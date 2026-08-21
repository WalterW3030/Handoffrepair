# evidence/ — push logs & evidence bundles here for me to inspect

Push any file I need to check (staging logs, serve logs, evidence tarballs, error output)
into this folder on YOUR machine, commit, and push. I'll read them from GitHub.

  cd /ephemeral/hr/Handoffrepair
  cp staging_evidence_*.tar.gz evidence/        # or: cp staging_evidence/<ts>/serve_qwen3-32b.log evidence/
  git add evidence/ && git commit -m "evidence: <what>" && git push origin master

Small text logs: commit the file directly. Large tarballs (>~25MB): tell me first
(GitHub file limits); we may split or use a release instead.
