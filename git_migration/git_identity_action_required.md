# Git identity resolution

Audit date: 2026-08-12 (Asia/Shanghai)

## Observed configuration

| Scope | `user.name` | `user.email` |
|---|---|---|
| Global | not set | not set |
| Repository local | `hibiscus1031` | `2623839613@qq.com` |

The current audited commit is `ecc529a6c248946c609089cdf8cfc8ef78eadfcf`. Its author and committer identity is `谢槿博 <xiejinbo@Jinbo-Mac.local>`. This host-derived address is historical metadata and is not accepted as the future publishing identity.

GitHub CLI authentication was completed for account `hibiscus1031`. The GitHub authenticated-email API returned `2623839613@qq.com` as the unique primary, verified, publicly visible email. The GitHub profile name is unset, so the explicit account login `hibiscus1031` is used as the repository-local author name. Global Git identity remains unchanged.

## Applied repository-local identity

```bash
git -C /Users/xiejinbo/Documents/SPH-PIO-PoC config --local user.name "hibiscus1031"
git -C /Users/xiejinbo/Documents/SPH-PIO-PoC config --local user.email "2623839613@qq.com"
git -C /Users/xiejinbo/Documents/SPH-PIO-PoC config --local --get user.name
git -C /Users/xiejinbo/Documents/SPH-PIO-PoC config --local --get user.email
```

This setting applies only to future commits in this repository and does not alter existing history. The audited baseline was not amended or rewritten.
