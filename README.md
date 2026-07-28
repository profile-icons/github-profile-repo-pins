# GitHub Profile Repository Pins

Design & display any public & private repository pin visualizations for GitHub user & organization profiles with i18n auto-translations, images, themes, dynamic ordering & optional statistics support.

Pin visualizations can be customized by any repository selection, dynamic ordering, background imagery (URL or path), and themes.

Pin visualizations for private repositories automatically link to deployed public Pages if the link is set to the repository.

Pin visualization detect browser language and automatically translate to multiple languages - may require refreshing browser cache.

Integrate with GitHub Pages deployed profile sites. A demonstration is found here: [https://r055a.github.io/r055a](https://r055a.github.io/r055a)

[![example-1](https://raw.githubusercontent.com/R055A/R055A/refs/heads/main/imgs/0.svg)](https://github.com/R055A/R055A) 
[![example-2](https://raw.githubusercontent.com/R055A/R055A/refs/heads/main/imgs/1.svg)](https://github.com/R055A/R055A)   
[![example-3](https://raw.githubusercontent.com/R055A/R055A/refs/heads/main/imgs/2.svg)](https://github.com/R055A/R055A) 
[![example-4](https://raw.githubusercontent.com/R055A/R055A/refs/heads/main/imgs/3.svg)](https://github.com/R055A/R055A) 

## Instructions

Basic, instant setup for default public repository pin visualizations. No PAT required. Secrets are only required for displaying pins for private repositories and certain customization.

### Actions Workflow

Copy the workflow to `.github/workflows/<workflow>.yaml` in a user/organization profile repository:

```yaml
name: generate-profile-repo-pins

on:
  schedule:
    - cron: "0 0 * * *"
  workflow_dispatch:

permissions:
  contents: write

jobs:
  update-pins:
    runs-on: ubuntu-latest
    steps:
      - uses: profile-icons/readme-repo-pins@v1
        with:
          gh_api_token: ${{ secrets.GH_API_TOKEN || secrets.GITHUB_TOKEN }}  # required, uses default fallback
          gh_username: ${{ secrets.GH_USERNAME || github.repository_owner }}  # required, uses default fallback
          theme: ${{ secrets.THEME }}  # optional
          background_image: ${{ secrets.BG_IMG }}  # optional
          num_repo_pins: ${{ secrets.NUM_REPO_PINS }}  # optional
          repo_pin_order: ${{ secrets.REPO_PIN_ORDER }}  # optional
          repo_names_exclusive: ${{ secrets.REPO_NAMES_EXCLUSIVE }}  # optional
          is_exclude_repos_owned: ${{ secrets.IS_EXCLUDE_REPOS_OWNED }}  # optional
          is_exclude_repos_contributed: ${{ secrets.IS_EXCLUDE_REPOS_CONTRIBUTED }}  # optional
          is_contribution_stats: ${{ secrets.IS_CONTRIBUTION_STATS }}  # optional
 
```

> The workflow execute the [action.yml](https://github.com/profile-icons/readme-repo-pins/blob/main/action.yml) and source code in this repo.

### Template Profile

* Simply create a copy of the template repository by clicking [here](https://github.com/new?template_name=readme-repo-pins-template&template_owner=profile-icons)
  * name the new repository `Repository name*` identical to the `owner*` name.
  * select the green `Create Repository` button.

> The [template repo](https://github.com/profile-icons/readme-repo-pins-template) (and generated copies) execute the source code in this repo.

The source code creates a profile with frequently updated repo pins using CI automation and a placeholder:

```
<!-- START: REPO-PINS -->
<!-- END: REPO-PINS -->
```

If you want an auto-updated GitHub profile, ensure the placeholder is in a `README.md` file.  
If you want a GitHub Pages profile, ensure the placeholder is in an `index.md` file.
The files should be located in:
  * `/` root directory for GitHub user profile and GitHub Pages profile
  * `/profile` directory for a GitHub organisation profile.  

There is no further setup requirement aside for optional configurations.

## Configurations (optional)

The repository project was initially created to streamline the display of generated pin visualizations on a 
private profile `README.md`, but supports broader use cases with optional personalization and elevation of API privileges.

### Theme

The optional `THEME` configuration controls the visual color scheme of the generated SVG pin background, border, text, and icon features.

This can be set by creating a [GitHub Action](https://docs.github.com/en/actions) with the following key-value field pairs:
* key: `THEME`
* value (either one of the two formats):
  * `{<owner/repo>: <theme_name>,...,<owner/repo>: <theme_name>}` - individual pin theme(s)
  * `<theme_name>` - single theme for pin(s)

where:
* `owner/repo` matches the owner/repository names in the URL of a given repository - required `<>`
* `theme_name` matches any key in `files/themes.json` - required `<>`

> If a theme is unavailable, you can add it to `files/themes.json` - refer [here](https://github.com/profile-icons/readme-repo-pins/issues/1) for more information.

> The default `THEME` is `github_soft`

### Background Image

The optional `BG_IMG` configuration controls the embedding of select imagery to the background of the generated SVG pin(s).

This can be set by creating a [GitHub Action](https://docs.github.com/en/actions) with the following key-value field pairs:
* key: `BG_IMG`
* value (either one of the three formats):
  * `{<owner/repo>: <img-config-dict>,...,<owner/repo>: <img-config-dict>}` - individual pin background image(s)
  * `<img-config-dict>` - single background image for pin(s)
  * `<url/filepath>` - single background image for pin(s)

where:
* `owner/repo` matches the owner/repository names in the URL of a given repository - required `<>`
* `img-config-dict` is any stringified dictionary configuration matching the following format
```
{
    "img": <url/filepath>, 
    "align": [align], 
    "mode": [mode], 
    "opacity": [opacity]
}
```
* `url/filepath` is either an image URL or the path to an image file uploaded (to an owned repo) - required `<>`
* `align` is any align keyword value in [preserveAspectRatio](https://developer.mozilla.org/en-US/docs/Web/SVG/Reference/Attribute/preserveAspectRatio#syntax) attribute - optional `[]` (default `xMidYMid`)
* `mode` is any [CSS object-fit](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Properties/object-fit) property value in `[cover, contain, stretch]` - optional `[]` (default `stretch`)
* `opacity` is a float value between `0` and `1.0` - optional `[]` (default `0.25`)

> The default `BG_IMG` is `None` (which defaults to the `THEME` background color)

### Repository List

The optional `REPO_NAMES_EXCLUSIVE` configuration controls the exclusive generation of pins for a given list of repository names.

This can be set by creating a [GitHub Action](https://docs.github.com/en/actions) with the following key-value field pairs:

* key: `REPO_NAMES_EXCLUSIVE`
* value: `<owner/repo>,...,<owner/repo>`

where:
* `owner/repo` matches the owner/repository names in the URL of a given repository - required `<>`
* `<owner/repo>,...,<owner/repo>` is a list of any number of `owner/repo` separated by commas `,`

### Contribution Stats

The optional `IS_CONTRIBUTION_STATS` configuration controls whether a (user) contribution percentage is appended to 
the repository contributor count in the pin footer, enclosed in parentheses, such as: ![ICON](https://raw.githubusercontent.com/primer/octicons/refs/heads/main/icons/people-16.svg) 22 (99.9%).

This can be set by creating a [GitHub Action](https://docs.github.com/en/actions) with the following key-value field pairs:

* key: `IS_CONTRIBUTION_STATS`
* value: `[is_stats]`

where:
* `is_stats` is either `true` (any value) or `false` (empty) - optional `[]`

> The default `IS_CONTRIBUTION_STATS` is `false`

### API Token

The optional `GH_API_TOKEN` configuration is for elevating GitHub GraphQL API privileges with a [personal access token (PAT)](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens)
The default [rate limit](https://docs.github.com/en/graphql/overview/rate-limits-and-query-limits-for-the-graphql-api) when not using a GitHub PAT is 1000 query points per hour and is limited to public repository data. 
The rate limit when using a PAT is increased to 5000, and provides access to authorized private repository data so that pins can be generated for both
public and private repositories to both public and private profiles.

This can be set by creating a [GitHub Action](https://docs.github.com/en/actions) with the following key-value field pairs:

* key: `GH_API_TOKEN`
* value: `[PAT]`

where:
* `PAT` is a GitHub personal access token and can be generated [here](https://github.com/settings/tokens) - optional `[]`

> The default `GH_API_TOKEN` is `GITHUB_TOKEN` (1000 GraphQL API query points per hour)

> A `PAT` is required for displaying private repository pins

### Number

The optional `NUM_REPO_PINS` configuration controls the maximum possible numb[README.md](README.md)er of repository pins to generate up to a hard limit of `100`.

This can be set by creating a [GitHub Action](https://docs.github.com/en/actions) with the following key-value field pairs:

* key: `NUM_REPO_PINS`
* value: `[num]`

where:
* `num` is any int value greater than `0` - optional `[]`

> The default `NUM_REPO_PINS` is `6`

> Overruled by the `REPO_NAMES_EXCLUSIVE` configuration when default, or the minimum value between both when also set.

### Order

The optional `REPO_PIN_ORDER` configuration controls the dynamic ordering of generated repository pin visualizations.

This can be set by creating a [GitHub Action](https://docs.github.com/en/actions) with the following key-value field pairs:

* key: `REPO_PIN_ORDER`
* value: `[order]`

where:
* `order` is optionally any value in:
  * `stargazers` - the number of stars the repo has
  * `name` - the repo name
  * `created_at` - the datetime the repo is initially created
  * `updated_at` - the datetime the repo is last updated
  * `pushed_at` - the datetime the repo is last pushed to
  * `random` - any random order

> The default `REPO_PIN_ORDER` is `STARGAZERS`

> Overruled by the `REPO_NAMES_EXCLUSIVE` configuration when default, but not when also set.

### Exclude Owned Repositories (Not Pinned)

By default, repository data collected for generating pin visualizations is first those pinned by a user, followed by
other repositories owned by the user, and then other repositories the user has contributed to but does not own.

The optional `IS_EXCLUDE_REPOS_OWNED` configuration controls whether repositories owned by a user but not pinned are excluded.

This can be set by creating a [GitHub Action](https://docs.github.com/en/actions) with the following key-value field pairs:

* key: `IS_EXCLUDE_REPOS_OWNED`
* value: `[is_exclude]`

where:
* `is_exclude` is either `true` (any value) or `false` (empty) - optional `[]`

> The default `IS_EXCLUDE_REPOS_OWNED` is `false`

> Overruled by the `REPO_NAMES_EXCLUSIVE` configuration, as pin visuals are generated only for listed repositories.

### Exclude Contributed Repositories (Neither Owned Nor Pinned)

By default, repository data collected for generating pin visualizations is first those pinned by a user, followed by
other repositories owned by the user, and then other repositories the user has contributed to but does not own.

The optional `IS_EXCLUDE_REPOS_CONTRIBUTED` configuration controls whether repositories contributed to but not owned by a user are excluded.

This can be set by creating a [GitHub Action](https://docs.github.com/en/actions) with the following key-value field pairs:

* key: `IS_EXCLUDE_REPOS_CONTRIBUTED`
* value: `[is_exclude]`

where:
* `is_exclude` is either `true` (any value) or `false` (empty) - optional `[]`

> The default `IS_EXCLUDE_REPOS_CONTRIBUTED` is `false`

> Overruled by the `REPO_NAMES_EXCLUSIVE` configuration, as pin visuals are generated only for listed repositories.

### Username

The optional `GH_USERNAME` configuration controls which (pinned/owned/contributed to) repositories are displayed by association.

This can be set by creating a [GitHub Action](https://docs.github.com/en/actions) with the following key-value field pairs:

* key: `GH_USERNAME`
* value: `[username]`

where:
* `username` must match the username associated with repositories pinned/owned/contributed to by the user the pin display focuses on - optional `[]`

> The default `GH_USERNAME` is `github.repository_owner` (the username associated with the owner of the repo)

> `GH_USERNAME` is required for displaying pins on an organisation profile
