# Licenses and third-party notices

Researcher is the Python distribution and command name of this project, historically
called Infinibay. The existing `LICENSE.md` declares **AGPL-3.0-or-later** and retains
the historical Infinibay LLC copyright notice. This modernization does not change
that license, transfer copyright or relicense third-party components.

## What accompanies each artifact

- The Researcher wheel and source distribution include `LICENSE.md` and this file.
  The wheel declares dependencies; it does not bundle their Python distributions.
  Preserve the dependency distributions' license and notice files when distributing
  an installed environment, container or other combined artifact.
- Each production web build generates `assets/THIRD_PARTY_LICENSES.md` from the
  packages included in its JavaScript bundles, with Vite's license collector.
  It also includes the unchanged project license at `assets/PROJECT_LICENSE.txt`.
  Keep both files with the build. The server's existing `/assets` route serves them;
  generated JavaScript points to the dependency notice file.
- The complete lock inventory includes optional platforms and development tools.
  It is broader than the web bundle and is not a list of libraries all shipped
  together. Ken and the historical Chroma exporter have separate dependency scopes.

## Reproduce the evidence

```sh
python3 scripts/audit_dependencies.py --licenses-only --output /tmp/researcher-licenses-new
```

Use a new directory. The auditor reads version-specific registry declarations.
For missing npm declarations it checks the exact archive against the lock's
integrity before reading `package.json`; it neither installs nor runs the archive.
For missing Python declarations it reads a digest-verified source archive and
requires an explicit review bound to the archive and license-file hashes.
Missing evidence, failed downloads and unreviewed source licenses fail the license
inventory command. This is evidence collection, not an automatic compatibility
decision. `--licenses` includes the same checks in the full vulnerability audit.

The current evidence and specific source reviews live in
`docs/modernization/dependencies-final-evidence/licenses.json` and
`docs/modernization/license-artifact-reviews.json`. A changed lock requires a new
inventory. A changed reviewed artifact requires a new review.

## Distribution decisions still required

The final release must retain notices for the actual shipped artifacts, including
vendored native code, non-JavaScript assets, fonts and downloaded model files where
applicable. The package declaration inventory alone does not establish those
components' complete license coverage or compatibility.

MIT/BSD notices and Apache license/NOTICE requirements must be preserved for the
included components. MPL-covered files may require corresponding source and
source-availability notices when distributed. `tld` declares alternatives
`MPL-1.1 OR GPL-2.0-only OR LGPL-2.1-or-later`; this is not a GPL-2.0-only selection.
Review the chosen alternative in the actual release context. See the
[Mozilla distribution guidance](https://www.mozilla.org/en-US/MPL/2.0/FAQ/) and the
upstream license texts retained with each package.

The project license's source-provision requirements also apply as specified in
`LICENSE.md`, including its section 13 for modified versions used over a network.
Before distribution or deployment, provide the corresponding source for the exact
version offered to users. Local unpublished commits are not an available public
source release. No publication or deployment is performed by generating notices.

Vite's collector and Python package metadata follow their documented formats:
[Vite build.license](https://vite.dev/config/build-options#build-license) and
[Python license metadata](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/#license-and-license-files).
