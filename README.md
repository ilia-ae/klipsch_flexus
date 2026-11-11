# ci-results

Written by the workflow "Verify signed local CI" (.github/workflows/local-ci.yaml)
after it verified the owner's signed local CI evidence for a push to main.
Do not edit: every update replaces this branch with one new commit.

- badges/*.json: shields.io endpoint badges, built from the verified evidence.
- evidence/<sha>.json and .sig: the signed evidence (exact bytes) and its SSH
  signature; latest.json is the newest verified commit on main.
- allowed_signers: the trust root the workflow verified with
  (repository variable LOCAL_CI_ALLOWED_SIGNERS).

Check a signature (principal code@ilia.ae, namespace klipsch-flexus-local-ci@ilia.ae):

    ssh-keygen -Y verify -f allowed_signers -I code@ilia.ae -n klipsch-flexus-local-ci@ilia.ae \
      -s evidence/latest.json.sig < evidence/latest.json

scripts/verify_local_ci.py in ilia-ae/klipsch_flexus also checks that the evidence
matches the commit, its tree and its policy (see docs/TESTING.md).
