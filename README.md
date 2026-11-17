# Musicvid — Thai AI singer test

An 8-second Thai singing lip-sync experiment using PiAPI and GitHub Actions.

## Setup
1. In **Settings → Secrets and variables → Actions**, create repository secret `PIAPI_KEY`.
2. Host the generated singer image and an **8-second** excerpt of your own song at direct HTTPS URLs accessible by PiAPI. Never put private media or API keys in this public repository.
3. Open **Actions → Thai singer test → Run workflow** and paste the two URLs.
4. The workflow submits the video-generation job, waits for it, submits a lip-sync job using the generated video's task ID, then downloads the result as an Actions artifact.

**Costs:** Running the workflow submits paid PiAPI tasks. Check your model pricing and account balance before running. The workflow does not run automatically.

**Compatibility:** PiAPI's Kling input schemas and model availability can change. This starter uses Kling 2.6 video generation and the lip_sync task with origin_task_id/local_dubbing_url; inspect API errors and adjust against your current PiAPI docs if necessary.

Your original full song is not uploaded to GitHub. Only use an 8-second audio excerpt for this test.
