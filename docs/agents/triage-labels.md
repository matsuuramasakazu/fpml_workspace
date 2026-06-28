# Triage Labels

The skills speak in terms of five canonical triage roles. This file maps those roles to the actual label strings used in this repo's issue tracker.

| Label in mattpocock/skills | Label in our tracker | Meaning                                  |
| -------------------------- | -------------------- | ---------------------------------------- |
| `needs-triage`             | (None / `bug` / `enhancement`) | Maintainer needs to evaluate this issue. Note: `needs-triage` label does not exist by default in this repo. |
| `needs-info`               | (None / `question`)  | Waiting on reporter for more information. Note: `needs-info` label does not exist by default in this repo. |
| `ready-for-agent`          | `ready-for-agent`    | Fully specified, ready for an AFK agent  |
| `ready-for-human`          | (None)               | Requires human implementation            |
| `wontfix`                  | `wontfix`            | Will not be actioned                     |

> [!IMPORTANT]
> If you specify a label that does not exist when creating an GitHub issue, it will result in an error. Be sure to run `gh label list` before creating or editing an issue, and apply only labels that exist.
