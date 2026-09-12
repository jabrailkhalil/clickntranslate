# Platform rules checked for this campaign

Checked on 2026-09-04. Rules can change; open every linked page again at the
moment of submission.

## AlternativeTo

- A verified email address is required to suggest a new app.
- Use **Suggest new application** and fill in platforms, license, descriptions,
  and tags. Submissions enter a review queue.
- AlternativeTo links to the official download site; it does not host the
  installer.
- Do not use a user profile as an advertisement.

Official source: https://alternativeto.net/faq/

## Product Hunt

- Post from a personal account, not a company account.
- The primary URL should lead directly to the product, not to a press article.
- The description is limited to 260 characters.
- A visible gallery requires at least two images; the recommended gallery size
  is 1270 x 760.
- Only full YouTube URLs are supported for gallery video.
- Prepare a first comment and include the maker account.
- Product Hunt recommends a live, usable product. A newly created personal
  account may have to complete onboarding and wait before it can post.

Official sources:

- https://help.producthunt.com/en/articles/479557-how-to-post-a-product
- https://help.producthunt.com/en/articles/9883485-product-hunt-featuring-guidelines
- https://help.producthunt.com/en/articles/481909-how-can-i-get-access-to-post

## Show HN

- The title must begin with `Show HN:`.
- Link to something people can actually try. A signup or email gate hurts the
  submission, and a landing page alone is not a Show HN.
- Explain what was built, why, and what is technically interesting.
- The maker should be present to answer questions.
- Do not ask friends or followers to upvote or comment.
- A minor version announcement is normally not substantial enough. Present the
  mature project and its technical approach, not “v1.7.0 is out.”

Official source: https://news.ycombinator.com/showhn.html

## Habr

- Use a narrative technical article whose subject is clear from the title.
- A promotional article belongs in the appropriate hub, including “Я пиарюсь”
  when applicable; Habr does not allow two consecutive publications in that hub.
- Habr states that generated material should be only a small part of a large,
  useful technical article. The supplied file is therefore an editorial
  scaffold: the author must add first-hand details, screenshots, measurements,
  and rewrite it in their own words before publication.

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

`r/github` currently directs promotion to its recurring self-promotion
megathread rather than individual promotional posts. Treat the other four
drafts as conditional until their current sidebar rules are confirmed.

## WinGet

- Create manifests that follow the Windows Package Manager schema.
- Use a stable, versioned installer URL and SHA-256.
- Run `winget validate` and test installation in Windows Sandbox.
- Submit the manifest to `microsoft/winget-pkgs`; automated validation and
  manual review follow.
- Microsoft can reject a package, including on security-policy grounds. Resolve
  current antivirus false positives before treating WinGet as a guaranteed
  channel.

Official sources:

- https://learn.microsoft.com/en-us/windows/package-manager/package/manifest
- https://learn.microsoft.com/en-us/windows/package-manager/package/repository
