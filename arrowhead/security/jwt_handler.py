"""JWT handling for the Arrowhead Framework."""

import json
from typing import Any, Dict

import jwt
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jwcrypto import jwe, jwk


class JWTHandler:
    """JWT and JWE handling for Arrowhead Framework."""

    @staticmethod
    def load_rsa_private_key(filename: str) -> rsa.RSAPrivateKey:
        """Load RSA private key from PEM file."""
        with open(filename, "rb") as key_file:
            private_key = serialization.load_pem_private_key(
                key_file.read(), password=None, backend=default_backend()
            )

        if not isinstance(private_key, rsa.RSAPrivateKey):
            raise ValueError("Not an RSA private key")

        return private_key

    @staticmethod
    def load_rsa_public_key(filename: str) -> rsa.RSAPublicKey:
        """Load RSA public key from PEM file."""
        with open(filename, "rb") as key_file:
            public_key = serialization.load_pem_public_key(
                key_file.read(), backend=default_backend()
            )

        if not isinstance(public_key, rsa.RSAPublicKey):
            raise ValueError("Not an RSA public key")

        return public_key

    @staticmethod
    def parse_rsa_public_key_from_pem(pem_string: str) -> rsa.RSAPublicKey:
        """Parse RSA public key from PEM string."""
        public_key = serialization.load_pem_public_key(
            pem_string.encode(), backend=default_backend()
        )

        if not isinstance(public_key, rsa.RSAPublicKey):
            raise ValueError("Not an RSA public key")

        return public_key

    @staticmethod
    def decrypt_jwe(encrypted_jwt: str, private_key: rsa.RSAPrivateKey) -> str:
        """Decrypt a JWE token using RSA private key."""
        # Convert to JWK format for jwcrypto
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )

        jwk_key = jwk.JWK.from_pem(private_pem)

        # Decrypt the JWE
        jwe_token = jwe.JWE()
        jwe_token.deserialize(encrypted_jwt)
        jwe_token.decrypt(jwk_key)

        return jwe_token.payload.decode("utf-8")

    @staticmethod
    def verify_jwt(token_string: str, public_key: rsa.RSAPublicKey) -> Dict[str, Any]:
        """Verify JWT signature and return payload."""
        # Convert public key to PEM format
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        try:
            payload = jwt.decode(token_string, public_pem, algorithms=["RS256"])
            return payload
        except jwt.InvalidTokenError as e:
            raise ValueError(f"Invalid JWT token: {e}")

    @staticmethod
    def create_jwt(payload: Dict[str, Any], private_key: rsa.RSAPrivateKey) -> str:
        """Create a JWT token signed with RSA private key."""
        # Convert private key to PEM format
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )

        token = jwt.encode(payload, private_pem, algorithm="RS256")
        return token
