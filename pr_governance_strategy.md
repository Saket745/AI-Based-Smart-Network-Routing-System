# Pull Request Governance Strategy

## 1. Analysis of Current PR Workflows

The current CI configuration validates **every commit** in a Pull Request:

```bash
for commit in $(git log --format=%H origin/${{ github.base_ref }}..HEAD); do
  commit_msg=$(git log --format=%B -n 1 $commit)
  python scripts/validate_commit_msg.py "$commit_msg"
done
```

### Challenges with "Every Commit" Validation
1.  **Iterative Development**: AI agents and human developers often create "WIP" or "Save" commits during development. Forcing conventional commits on every intermediate step increases friction.
2.  **Rebase/Squash Issues**: If a developer rebases or fixes a commit message locally, they must force-push.
3.  **Governance Blockers**: A single poorly formatted commit early in a long history can block a PR even if the final state is perfect.

## 2. Recommendation: Final PR State Validation

Governance should prioritize the **Final PR State** (PR Title and Description) over individual intermediate commits, *provided* that a squash-merge policy is enforced.

### Proposed Recommendation
- **PR Title**: Must follow Conventional Commits format.
- **Merge Policy**: Enforce **Squash and Merge**. This ensures that the history of the target branch (`main`) remains clean and conventional, regardless of how messy the feature branch was.
- **Commit Validation**:
    - For `push` to `main`: Validate the single commit (which is the result of the squash).
    - For `pull_request`: Validate the **PR Title** instead of every individual commit. This allows for rapid iteration while guaranteeing a clean final history.

## 3. Recommended PR Policies

| Policy | Setting | Reason |
|--------|---------|--------|
| **PR Title** | Required | Must match `<type>(<scope>): <desc>` |
| **Merge Method** | Squash | Keeps `main` history clean and linear. |
| **Auto-Merge** | Allowed | If all CI checks pass and 1 approval is met. |
| **Delete Branch**| Enabled | Cleanup after merge. |
| **CI Validation**| PR Title | Use a GitHub Action like `amannn/action-semantic-pull-request`. |

## 4. Modified Commit Governance
If the team still desires individual commit validation, the validator should be updated to be less strict for non-main branches (e.g., allow `wip` or `fixup!`). However, validating the PR title is the industry standard for enterprise-grade repositories using squash merges.
