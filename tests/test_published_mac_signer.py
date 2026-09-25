"""Release tooling must keep the identity used by the published Mac packages."""
from tools import macos_ci_signing, stage_macos_artifacts


def test_repository_certificate_matches_published_identity():
    assert macos_ci_signing.EXPECTED_SHA1 == 'FC6752F0026D34E5B63433544AF788B8FC1899EF'
    assert macos_ci_signing.validate_certificate().startswith('-----BEGIN CERTIFICATE-----')


def test_packaging_and_verification_use_the_same_identity():
    assert stage_macos_artifacts.EXPECTED_SIGNER == macos_ci_signing.EXPECTED_SHA1
    assert macos_ci_signing.EXPECTED_SHA1.lower() in macos_ci_signing.requirement()
