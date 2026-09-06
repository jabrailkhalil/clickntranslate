# Windows code signing

## Current status

The next source version is **1.7.1**. The inspected local 1.7.0 release stage has
five unsigned project executables. No code-signing certificate was available in
the Windows CurrentUser/My or LocalMachine/My stores during the 2026-09-05 check.
The scripts below prepare and verify signing; no trusted signature has been
created and no certificate has been purchased. On 2026-09-05 the maintainer's
application for the free SignPath Foundation program was sent through Gmail to
the official support@signpath.io contact. Gmail confirmed sending. After the
local VPN connection was repaired, the official Foundation application form
was also submitted on the same day and confirmed "Form submitted". The form
explicitly referenced the earlier email so the requests can be associated.
Approval is pending; no certificate has been issued. No antivirus sample
submissions have been sent by this change.

File version, publisher strings and SHA-256 checksums are useful metadata. They
are **not** Authenticode signatures. A self-signed development certificate is
not suitable for distributing the app publicly. A trusted signature identifies
the publisher and protects the signed bytes; antivirus classification and
SmartScreen reputation remain separate checks.

## Obtain a trusted signing identity

For this GPL-3.0 open-source project, an application has been sent to
[SignPath Foundation](https://signpath.org/apply). It offers free signing to
accepted projects, subject to its [conditions](https://signpath.org/terms).
Acceptance and service configuration are required; this repository does not
currently have an approved SignPath integration. Its signing service must be
connected to a verifiable build pipeline after approval, using the actual
organization/project identifiers returned by the service.

The application included the following project information. The first request
used the [official first-contact support address](https://signpath.io/support)
because a local VPN issue prevented the form from loading. The subsequent
website submission used the Foundation application form directly. It disclosed
that Windows releases are currently built locally and that verifiable CI,
signing roles and project attribution still need to be configured during
onboarding. Optional marketing consent was left unchecked.

| Field | Value |
| --- | --- |
| Project | Click'n'Translate |
| Repository | https://github.com/jabrailkhalil/clickntranslate |
| License | GPL-3.0-only |
| Maintainer account | jabrailkhalil |
| Description | Windows and Linux desktop screen OCR and translation application, with local and online translation, global shortcuts, document translation and optional autostart. |
| Requested artifacts | Windows launcher, main application, ArgosWorker, OcrWorker, updater, installer and uninstaller. |
| Privacy information | [PRIVACY.md](../PRIVACY.md) |
| Contact and signing approvers | The maintainer's name, contact email and proposed approver role were included privately in the application. |

Do not claim SignPath sponsorship, invent account identifiers, or publish its
required attribution before acceptance. A certificate issued by a public CA is
another option; eligibility, identity verification and price depend on the
provider. Microsoft's [comparison](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/code-signing-options)
describes the available routes, including geographic limits for Artifact Signing.

## Local certificate or hardware-token workflow

Use a certificate with code-signing usage and an accessible private key in the
Windows certificate store. The key may remain on a hardware token; install its
vendor middleware. The scripts select an explicit public thumbprint and never
export a private key or request its password as a command-line parameter.
Install Windows SDK SignTool and Inno Setup 6 first.

```powershell
# Show public metadata only; choose the certificate issued to the publisher.
Get-ChildItem Cert:\CurrentUser\My -CodeSigningCert |
    Select-Object Subject, Thumbprint, NotAfter, HasPrivateKey

$thumbprint = 'REPLACE_WITH_YOUR_CERTIFICATE_THUMBPRINT'

# Fails before building if the certificate or signing tool is unavailable.
./tools/stage_release.ps1 -Version 1.7.1 -RequireSignature `
    -CertificateThumbprint $thumbprint

# The stage signs only our five EXEs, preserving upstream DLL signatures.
$package = './releases/ClicknTranslate-v1.7.1-win64-stage/ClicknTranslate'
./tools/sign_windows.ps1 -Mode Verify -PackageRoot $package `
    -CertificateThumbprint $thumbprint

# Inno signs its embedded uninstaller and the final installer during compilation.
./tools/build_signed_installer.ps1 -PackageRoot $package `
    -CertificateThumbprint $thumbprint
```

For a machine-store certificate, pass `-CertificateStoreLocation LocalMachine`
to the stage and installer scripts. Signing uses SHA-256 and an RFC 3161
timestamp; verification requires a trusted signature, a timestamp and the same
certificate across the project executables. The report contains each file's
SHA-256, version and signature state. Failure stops the signed build.

Optional separately distributed repair/network/bootstrap EXEs must also be signed
with `sign_windows.ps1 -FilePath ...` before embedding or archiving them. A ZIP
does not carry Authenticode: sign its contained EXEs first, then create the ZIP
and calculate its final SHA-256. Repacking, rebuilding or changing resources
after signing requires signing and hashing again. Keep checksums/signature
reports outside the portable payload so creating a report does not change it.

Build the optional update-repair helper only after the signed portable ZIP is
final. Its download URL is derived from `-Version`; its checksum is mandatory
and must not be copied from an earlier release:

```powershell
$archive = './releases/Click-n-Translate-1.7.1-windows-portable-x64.zip'
$archiveHash = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash
./tools/build_update_repair.ps1 -Version 1.7.1.0 -PackageSha256 $archiveHash
./tools/sign_windows.ps1 -FilePath './releases/ClicknTranslate-Update-Repair.exe' `
    -CertificateThumbprint $thumbprint
```

Distribute this helper separately: embedding it back into the ZIP would change
the archive whose hash it contains. A custom `-PackageUrl` must use HTTPS;
`file://` is accepted only to support local repair integration tests.

The signed-installer wrapper uses the public
`Click-n-Translate-1.7.1-windows-x64-installer.exe` filename, keeping it separate
from the optional network downloader's legacy filename.

To inspect an unsigned stage without modifying or signing any executable:

```powershell
./tools/sign_windows.ps1 -Mode Audit -PackageRoot $package `
    -ReportPath './releases/windows-signatures.json'
```

Direct unsigned staging remains available for development and prints a warning.
It must not be described as a signed release. Existing public download links
stay on 1.7.0 until actual 1.7.1 artifacts have passed release checks.

## Investigate antivirus reports

The starting report is [Multiple Alerts on VirusTotal, #5](https://github.com/jabrailkhalil/clickntranslate/issues/5).
Get the public report URL, scanned SHA-256, vendor names and full detection names.
Compare the archive hash against the official release and inspect each bundled
executable separately. A generic detection name alone does not establish that a
sample is safe or malicious.

Submit confirmed official samples for vendor analysis and track the result
against the exact submitted hash. Prepare the sample hash, version, download
link, source repository, build description and observed detection; attach the
file when the vendor requires it. Use the
[Microsoft submission portal](https://www.microsoft.com/en-us/wdsi/filesubmission)
or [ESET's submission instructions](https://support.eset.com/en/kb141-submit-a-virus-website-or-potential-false-positive-sample-to-the-eset-lab),
as applicable to the report. This change does not upload samples or send messages.
Do not disable antivirus or modify exclusions to produce a clean result.

## Technical references

- [Microsoft SignTool](https://learn.microsoft.com/en-us/windows/win32/seccrypto/signtool)
- [Inno Setup signing](https://jrsoftware.org/ishelp/topic_setup_signtool.htm)
- [Inno Setup signed uninstaller](https://jrsoftware.org/ishelp/topic_setup_signeduninstaller.htm)
- [PyInstaller version resources](https://pyinstaller.org/en/stable/usage.html#capturing-windows-version-data)
