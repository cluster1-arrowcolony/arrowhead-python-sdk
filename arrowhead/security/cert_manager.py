"""Certificate management for the Arrowhead Framework."""

import logging
import os
import shutil
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path

logger = logging.getLogger(__name__)


class CertManager(ABC):
    """Abstract base class for certificate managers."""

    @abstractmethod
    def create_system_keystore(
        self,
        root_keystore: str,
        root_alias: str,
        cloud_keystore: str,
        cloud_alias: str,
        system_keystore: str,
        system_dname: str,
        system_alias: str,
        san: str,
        password: str,
    ) -> None:
        """Create a system keystore."""
        pass

    @abstractmethod
    def get_public_key(self, keystore_path: str, password: str) -> str:
        """Get public key from keystore."""
        pass

    @abstractmethod
    def convert_p12_to_pem(
        self, p12_file: str, password: str, output_cert: str, output_key: str
    ) -> None:
        """Convert PKCS#12 file to PEM format."""
        pass


class OpenSSLCertManager(CertManager):
    """Certificate manager using OpenSSL."""

    def _run_openssl_command(self, *args: str) -> subprocess.CompletedProcess:
        """Run an OpenSSL command."""
        cmd = ["openssl"] + list(args)
        logger.debug(f"Running: {' '.join(cmd)}")
        return subprocess.run(cmd, check=True, capture_output=True, text=True)

    def create_system_keystore(
        self,
        root_keystore: str,
        root_alias: str,
        cloud_keystore: str,
        cloud_alias: str,
        system_keystore: str,
        system_dname: str,
        system_alias: str,
        san: str,
        password: str,
    ) -> None:
        del root_alias, cloud_alias, system_alias
        """Create a system keystore using OpenSSL."""
        logger.info(f"Creating system keystore {system_keystore} with OpenSSL")

        # Generate file names
        root_cert_file = str(Path(root_keystore).with_suffix(".crt"))
        cloud_cert_file = str(Path(cloud_keystore).with_suffix(".crt"))
        system_pub_file = str(Path(system_keystore).with_suffix(".pub"))

        # Temporary files
        csr_file = "csrfile.csr"
        signed_cert_file = "signed_cert.crt"
        system_key_file = str(Path(system_keystore).with_suffix(".key"))
        cloud_key_file = str(Path(cloud_keystore).with_suffix(".key"))

        # Use only the basename for the system keystore
        system_keystore = Path(system_keystore).name
        system_pub_file = Path(system_pub_file).name

        if os.path.exists(system_keystore):
            raise RuntimeError(f"System keystore {system_keystore} already exists")

        ext_file = None
        chain_file = None

        try:
            # 1. Generate the system RSA private key
            logger.debug("Generating system private key...")
            self._run_openssl_command("genrsa", "-out", system_key_file, "2048")

            # 2. Generate a certificate signing request (CSR) with the desired subject and SAN
            # FIX: Use system_dname directly as the subject. It should be in "CN=name" format.
            subj = f"/{system_dname}"
            logger.debug(f"Generating CSR for system certificate with subject: {subj}")
            self._run_openssl_command(
                "req",
                "-new",
                "-key",
                system_key_file,
                "-subj",
                subj, # Use the full subject string
                "-addext",
                f"subjectAltName={san}",
                "-out",
                csr_file,
            )

            # 3. Extract the cloud CA's key and certificate if not already available
            pass_arg = f"pass:{password}"
            logger.debug("Extracting cloud key from cloud PKCS#12 file...")
            self._run_openssl_command(
                "pkcs12",
                "-in",
                cloud_keystore,
                "-nocerts",
                "-nodes",
                "-passin",
                pass_arg,
                "-out",
                cloud_key_file,
            )

            if not os.path.exists(cloud_cert_file):
                logger.debug("Extracting cloud certificate from cloud PKCS#12 file...")
                self._run_openssl_command(
                    "pkcs12",
                    "-in",
                    cloud_keystore,
                    "-clcerts",
                    "-nokeys",
                    "-passin",
                    pass_arg,
                    "-out",
                    cloud_cert_file,
                )

            # 4. Create a temporary extension file to supply the subjectAltName when signing
            ext_file = "v3ext.cnf"
            # An Arrowhead system can be both a client and a server, so we add both EKUs.
            ext_content = f"""[v3_ext]
authorityKeyIdentifier=keyid,issuer
basicConstraints=CA:FALSE
keyUsage = critical, digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth, clientAuth
subjectAltName = {san}
"""
            with open(ext_file, "w") as f:
                f.write(ext_content)

            # 5. Sign the CSR with the cloud CA's key and certificate
            logger.debug("Signing CSR with cloud CA...")
            self._run_openssl_command(
                "x509",
                "-req",
                "-in",
                csr_file,
                "-CA",
                cloud_cert_file,
                "-CAkey",
                cloud_key_file,
                "-CAcreateserial",  # creates a file (e.g. cloudCertFile.srl) with the serial number
                "-out",
                signed_cert_file,
                "-days",
                "3650",
                "-extfile",
                ext_file,
                "-extensions",
                "v3_ext",
            )

            # 6. Build the certificate chain file
            # The chain file contains first the cloud certificate, then the root certificate
            chain_file = "chain.pem"
            chain_content = ""

            with open(cloud_cert_file, "r") as f:
                chain_content += f.read() + "\n"

            with open(root_cert_file, "r") as f:
                chain_content += f.read() + "\n"

            with open(chain_file, "w") as f:
                f.write(chain_content)

            # 7. Create the system PKCS#12 keystore
            # It bundles the system's private key, the signed certificate, and the CA chain
            logger.debug("Creating system PKCS#12 keystore...")
            self._run_openssl_command(
                "pkcs12",
                "-export",
                "-inkey",
                system_key_file,
                "-in",
                signed_cert_file,
                "-certfile",
                chain_file,
                "-out",
                system_keystore,
                "-passout",
                pass_arg,
            )

            # 8. Extract the system public key from the signed certificate
            logger.debug("Extracting system public key...")
            result = self._run_openssl_command(
                "x509", "-in", signed_cert_file, "-pubkey", "-noout"
            )

            with open(system_pub_file, "w") as f:
                f.write(result.stdout)

        finally:
            # 9. Clean up temporary files
            temp_files = [
                csr_file,
                signed_cert_file,
                ext_file,
                chain_file,
                f"{cloud_cert_file}.srl",
                cloud_key_file,
                system_key_file,
            ]
            for temp_file in temp_files:
                if os.path.exists(temp_file):
                    os.remove(temp_file)

        # In case the system public key file is still missing, extract it from the system keystore
        if not os.path.exists(system_pub_file):
            logger.debug("Extracting public key from system keystore...")
            temp_cert = "temp_cert.crt"
            try:
                self._run_openssl_command(
                    "pkcs12",
                    "-in",
                    system_keystore,
                    "-nokeys",
                    "-clcerts",
                    "-passin",
                    f"pass:{password}",
                    "-out",
                    temp_cert,
                )
                result = self._run_openssl_command(
                    "x509", "-in", temp_cert, "-pubkey", "-noout"
                )
                with open(system_pub_file, "w") as f:
                    f.write(result.stdout)
            finally:
                if os.path.exists(temp_cert):
                    os.remove(temp_cert)

    def get_public_key(self, keystore_path: str, password: str) -> str:
        """Get public key from PKCS#12 keystore using OpenSSL."""
        if not os.path.exists(keystore_path):
            raise RuntimeError(f"Keystore file {keystore_path} not found")

        try:
            # Extract certificate from PKCS#12
            cert_result = self._run_openssl_command(
                "pkcs12",
                "-in",
                keystore_path,
                "-clcerts",
                "-nokeys",
                "-passin",
                f"pass:{password}",
            )

            # Extract public key from certificate
            pub_key_result = subprocess.run(
                ["openssl", "x509", "-pubkey", "-noout"],
                input=cert_result.stdout,
                text=True,
                check=True,
                capture_output=True,
            )

            # Clean output: Remove headers and newlines for authentication info format
            public_key = pub_key_result.stdout.strip()
            public_key = public_key.replace("-----BEGIN PUBLIC KEY-----", "")
            public_key = public_key.replace("-----END PUBLIC KEY-----", "")
            public_key = public_key.replace("\n", "")

            return public_key

        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to extract public key: {e}")

    def convert_p12_to_pem(
        self, p12_file: str, password: str, output_cert: str, output_key: str
    ) -> None:
        """Convert PKCS#12 file to PEM format using OpenSSL."""
        try:
            # Extract certificate
            cert_cmd = [
                "openssl",
                "pkcs12",
                "-in",
                p12_file,
                "-out",
                output_cert,
                "-clcerts",
                "-nokeys",
                "-passin",
                f"pass:{password}",
            ]
            subprocess.run(cert_cmd, check=True)

            # Extract private key
            key_cmd = [
                "openssl",
                "pkcs12",
                "-in",
                p12_file,
                "-out",
                output_key,
                "-nocerts",
                "-nodes",
                "-passin",
                f"pass:{password}",
            ]
            subprocess.run(key_cmd, check=True)

        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to convert P12 to PEM: {e}")


def generate_subject_alternative_name(name: str) -> str:
    """Generate Subject Alternative Name for certificate."""
    return f"DNS:{name},DNS:{name}-ip,DNS:localhost,IP:127.0.0.1"


def load_cert_manager() -> CertManager:
    """Load an available certificate manager."""
    if shutil.which("openssl"):
        logger.debug("Using openssl as certificate manager")
        return OpenSSLCertManager()
    else:
        logger.error("openssl command not found. Please install OpenSSL.")
        raise RuntimeError("openssl command not found. Please install OpenSSL.")
