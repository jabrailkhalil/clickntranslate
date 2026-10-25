# Platform rules checked for this campaign

Reviewed on **2026-10-25** against the official sources below. Recheck the
submission form and rules before publishing. The Reddit sidebar rules are
listed for a separate account-level check, not marked as verified here.

The public product site is **https://translate.clickn.dev/**. The next release
is planned in about two weeks; its version number and exact date are not
announced. Current listings must describe available software and distinguish
planned changes from released features.

## AlternativeTo

- Click’n’Translate already has a **live listing**, confirmed during this audit.
  Update that existing entry; do not submit another application card.
- Keep its website, Windows/macOS/Linux/Android platforms, GPL license,
  descriptions and screenshots consistent with the available release.
- Use the application listing for product information, rather than turning the
  account profile into an advertisement.

Official source: https://alternativeto.net/faq/

## Product Hunt

- Post from a personal account, not a company account.
- The primary URL should lead directly to the product, not to a press article.
- Use a tagline of at most 60 characters and up to three relevant topics.
- Official pages currently disagree on a 260/500-character description limit.
  Prepare a version of at most 260 characters and follow the live form's limit.
- A visible gallery requires at least two images; the recommended gallery size
  is 1270 x 760.
- Only full YouTube URLs are supported for gallery video.
- Prepare a first comment and include the maker account.
- Use a live, usable product. A new personal account must complete onboarding;
  the access guide normally specifies a one-week wait. A private draft can be
  prepared before choosing a launch date.
- Organic submission is separate from paid promotion. No paid hunter or
  advertising purchase is needed for this plan.

Official sources:

- https://help.producthunt.com/en/articles/479557-how-to-post-a-product
- https://help.producthunt.com/en/articles/481909-how-can-i-get-access-to-post
- https://help.producthunt.com/en/articles/17350772-launch-guide
- https://www.producthunt.com/launch/preparing-for-launch

## Show HN

- The title must begin with `Show HN:`.
- Link to something people can actually try. A signup or email gate hurts the
  submission, and a landing page alone is not a Show HN.
- Explain what was built, why, and what is technically interesting.
- The maker should be present to answer questions.
- Do not ask friends or followers to upvote or comment.
- A minor version announcement is normally not substantial enough. Present the
  working project, its technical approach and a substantial development story.
- The current `showlim` notice restricts Show HN submissions while the site
  receives a large influx. Account eligibility cannot be assumed; participate
  genuinely and check the actual submission flow before scheduling a post.

Official sources:

- https://news.ycombinator.com/showhn.html
- https://news.ycombinator.com/showlim

## Habr

- The rules revised on 8 July 2026 prohibit texts generated in whole or in part,
  or written/edited with neural-network assistance. The stated exception is a
  small generated addition to a substantial, useful author-written technical
  article; it does not permit publishing an AI-written article after a light
  rewrite.
- Promotional publications are allowed in corporate blogs or **once** in the
  “Я пиарюсь” hub. The separate publication guide also prohibits consecutive
  posts in that hub. The stricter once-only rule must be respected.
- Ordinary articles should share the author's knowledge and experience, with
  real implementation details, screenshots and measurements.
- Do not automatically publish `habr-draft.md`. The author must control any
  original Habr article and confirm account/publication eligibility.

Official sources:

- https://habr.com/ru/docs/help/publications/
- https://habr.com/ru/docs/help/rules/

## Reddit

Reddit rules are community-specific and may be visible only to a logged-in user.
Use these campaign rules even if a community appears permissive:

- Do not paste the same post into several communities.
- Disclose that you are the developer.
- Lead with the problem, implementation, or a request for feedback.
- Use the required flair and a weekly self-promotion thread when the rules call
  for one.
- Participate in the community before and after posting.
- Never ask for upvotes.

Candidate rule pages to re-check:

- https://www.reddit.com/r/SideProject/about/rules/
- https://www.reddit.com/r/opensource/about/rules/
- https://www.reddit.com/r/software/about/rules/
- https://www.reddit.com/r/languagelearning/about/rules/
- https://www.reddit.com/r/github/about/rules/

The earlier campaign recorded a self-promotion megathread requirement for
`r/github`. Recheck it and every other community's current rules from the
intended account before using any existing draft.

## WinGet

- Search the catalog and open PRs first to avoid duplicate submissions.
- Follow the Windows Package Manager schema using a multi-file manifest set:
  version, default locale and installer files.
- Use a stable, versioned installer URL and SHA-256.
- Run `winget validate` and test installation in Windows Sandbox.
- Submit one package version per manifest-only PR to `microsoft/winget-pkgs`;
  automated validation and review follow.
- Microsoft can reject a package, including on security-policy grounds. Resolve
  current antivirus false positives before treating WinGet as a guaranteed
  channel.

Official sources:

- https://learn.microsoft.com/en-us/windows/package-manager/package/manifest
- https://learn.microsoft.com/en-us/windows/package-manager/package/winget-validation
- https://github.com/microsoft/winget-pkgs/blob/master/doc/Authoring.md

## Uptodown

- Registration and ordinary publication are free. The platform accepts Android,
  Windows and Mac applications; it supports APK, EXE and DMG files.
- Submit through the developer console as the author/distribution-rights holder,
  or claim an existing entry instead of creating a duplicate.
- Supply a working signed package, accurate description, screenshots and a
  square icon larger than 128 × 128 pixels. Preserve the existing Android
  signing identity for updates.
- Review includes functionality, rights and harmful-malware checks. Paid
  marketing services are separate from free publication and are outside this
  plan.

Official sources:

- https://support.uptodown.com/hc/en-us/articles/4424141383181-Basic-guide-to-register-and-publish-apps-on-Uptodown
- https://support.uptodown.com/hc/en-us/articles/360052792972-Uptodown-s-app-publication-criteria
- https://support.uptodown.com/hc/en-us/articles/360053260051-Supported-file-formats-on-Uptodown

## AppImageHub

- Check for an existing entry, then submit exactly one file in `data/` through
  a PR. Prefer the upstream repository URL; the catalog selects the latest
  suitable x86_64 AppImage from Releases.
- The package must use the supported type-2/SquashFS format, start without
  network access, support X11 and run on the oldest Ubuntu LTS still in standard
  support. Its desktop file must validate.
- Review includes an automated launch/screenshot check and maintainer review.
  This catalog links users to upstream downloads; it does not host a separate
  application release.

Official source:
https://github.com/AppImage/appimage.github.io#how-to-submit-appimages-to-the-catalog

## Channels requiring separate engineering or a human submission

### F-Droid

GPL licensing alone does not establish eligibility. F-Droid builds from source
and requires compatible free-software dependencies and a free build toolchain.
Audit ML Kit and every other Android dependency before proposing a build; a
separate free-software flavor may be needed. Uploading the current APK is not
the main repository's inclusion process.

Official source: https://f-droid.org/en/docs/Inclusion_Policy/

### Flathub

The current policy requires disclosure of included AI-generated material,
identifying the affected parts and approximate extent. It prohibits AI-generated
or AI-assisted manifests. AI agents must not open or automate submission PRs,
write their commit messages/descriptions/review interactions, or perform agent
reviews. Research is permitted; it does not authorize an agent-led submission.
A human maintainer must handle any future application and the Flatpak packaging
must first be made functional under its sandbox.

Official source:
https://docs.flathub.org/docs/for-app-authors/requirements#generative-ai-policy
