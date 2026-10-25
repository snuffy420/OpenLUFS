# Publish OpenLUFS on GitHub

The project and release archives are prepared locally. No remote repository is selected or created by the build tools.

`GitHub/OpenLUFS-1.3.0/` contains the clean upload tree. Upload its contents at the repository root, including `.github` and `.gitignore`; do not upload the enclosing versioned folder as an extra directory. Native processing executables are fetched by the build workflow and distributed with release packages, rather than committed to the repository.

1. Create a GitHub repository named `OpenLUFS` in your account.
2. From the project directory, initialize Git if needed and commit the project:

```powershell
git init -b main
git add .
git commit -m "Initial OpenLUFS release"
```

3. Copy the remote URL from your new repository, then run `git remote add origin YOUR_REPOSITORY_URL` and `git push -u origin main`. Replace the placeholder with the actual URL.
4. Create a draft release titled `OpenLUFS 1.3.0`, choose the tag `v1.3.0`, and upload the Windows x64 setup `.exe`, portable `.7z`, source `.7z`, their `.sha256`/`.sha` files, and SHA256SUMS.txt from `releases/`.
5. Preview the README and screenshots, complete listening and compatibility checks, then publish the release when ready.

The binary is excluded from Git history by `.gitignore`. The source release `.7z` includes the pinned FFmpeg binary for convenience; Git checkouts fetch both tools using `tools/fetch_ffmpeg.py` and `tools/fetch_mp3rgain.py`. Build artifacts belong in GitHub Releases, rather than normal commits.

The Actions workflow builds and tests Windows artifacts on pushes and pull requests. Artifacts can be downloaded from the workflow run. It does not automatically publish a public release.

## Dependency source and redistribution

Keep the bundled license texts and source notices with the executable. OpenLUFS source and build scripts are included in its source archive. Dependency licenses and source locations are recorded in THIRD_PARTY_NOTICES.md. Public binary distribution must satisfy the applicable licenses, including providing the complete corresponding sources/build materials required for GPL components and preserving LGPL rights for Qt. A list of upstream links is not itself a complete corresponding-source archive.

Before publishing binary releases, arrange a compliant corresponding-source distribution for the exact dependency binaries, including the GPL-enabled FFmpeg build's external libraries. This is separate from the OpenLUFS application source archive. The supplied source notices document provenance but do not claim that the third-party corresponding sources are already fully mirrored here.

For the contact page, see CONTACT.md. Configure GitHub Pages to publish main from the repository root. The contact page is not deployed by the build workflow.
