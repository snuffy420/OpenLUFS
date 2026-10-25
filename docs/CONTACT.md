# Publishing the contact page

1. Upload `docs/contact.html` and `assets/contact-button.svg` to the OpenLUFS repository. The page includes its own inline OpenLUFS logo and needs no separate image files.
2. In GitHub repository Settings → Pages, choose **Deploy from a branch**, branch **main**, folder **/ (root)**, then Save. Keep the root publishing folder so the README URL remains `https://snuffy420.github.io/OpenLUFS/docs/contact.html`.
3. Wait for the Pages deployment, then open that URL. The form submits to the owner's supplied Formspree endpoint, with subject **OpenLUFS contact**.
4. Confirm the form is active in the Formspree account and that its notification destination is configured. Messages are not stored in the repository.

The contact section is included in the full replacement README and separately in README-BLOCKS.md. GitHub sanitizes interactive forms out of README content; the button opens the hosted page instead. Automated tests mock submissions and do not send test messages to the live inbox.
