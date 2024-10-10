# dependabot report

dependabot report is a tool I wish I had, or at least thought so. Imagine
yourself working for a software company which has more than 10 repositories on
GitHub. GitHub sends you "Your Dependabot alerts for today" for 10 repositories
and as for the rest of repositories you're on your own. Happy click through!
Yes, in ideal world everything would be patched and updated immediately.
However, some of us aren't there yet.

![dependabot_report_demo][dependabot_report_demo]

dependabot report is a simple script which fetches data from GitHub API and
presents it as a static HTML page(minus bootstrap and GitHub avatars). And
that's pretty much it. Could it be more complex with more moving parts? It
absolutely could. However, this is good enough for PoC/demo and for now.

## Dependencies

* [Jinja2]
* [PyGithub]
* [bootstrap] which is loaded from their(!) CDN
* [GitHub avatars] which will be loaded directly from GitHub when report is
  viewed

## GitHub token and permissions

Currently only authentication via token is supported.

### Classic token

When used with classic token then at least `repo:public_repo` permission is
required. I guess that `repo` permission is required in order to access private
repositories since `repo:public_repo` limits access to only to public
repositories. I suggest to use fine-grained personal access token instead.

### Fine-grained personal access token

When used with fine-grained personal access token then read access to
dependabot alerts and metadata(which is mandatory anyway) is required.

Whether you grant access only to public, all or selected repositories, is up to
you.

## Usage

Read GitHub token from ENV variable:

```
export MY_TOKEN=123456
python3 dependabot_report.py \
    --github-token-provider 'env:MY_TOKEN' \
    --include-repo-owner \
    --output-file report.html
```

or read GitHub token from file:

```
python3 dependabot_report.py \
    --github-token-provider 'file:my-token.txt' \
    --include-repo-owner \
    --output-file report.html
```

## License

MIT

[Jinja2]: https://pypi.org/project/Jinja2/
[PyGithub]: https://pypi.org/project/PyGithub/
[bootstrap]: https://getbootstrap.com
[GitHub avatars]: https://docs.github.com/en/account-and-profile/setting-up-and-managing-your-github-profile/customizing-your-profile/personalizing-your-profile
[dependabot_report_demo]: ../assets/dependabot_report_demo.png?raw=true
