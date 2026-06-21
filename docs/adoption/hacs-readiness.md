# HACS Readiness Checklist

To maximize adoption, `ws_core` needs to be in the HACS default repository list. Being a custom repository is a massive friction point because users have to copy-paste the GitHub URL.

## Current State
The integration currently requires users to add it as a custom repository. While the `hacs.json` exists, it needs polish before submitting to the HACS default list.

## Checklist for HACS Default Submission

### 1. Repository Hygiene
- [ ] **GitHub Topics:** Ensure the repository has topics like `home-assistant`, `hacs`, `weather`, `ecowitt`, `integration`.
- [ ] **Description:** The GitHub About description must be concise. E.g., "The weather intelligence layer for Home Assistant. Turn raw station data into actionable nowcasts, local forecasts, and safety alerts."
- [ ] **`hacs.json` Verification:** Verify the `hacs.json` file contains `"name"`, `"render_readme"`, and `"homeassistant"` requirements. Add `"issue_tracker"` for completeness.

### 2. Branding
- [ ] **Brands Repository:** `ws_core` needs to be submitted to the `home-assistant/brands` repository so it has a proper, high-quality icon in the Home Assistant UI during setup. The current `icon.png` in the repo should be PR'd to the brands repo.

### 3. Code Quality & Linting
- [ ] **Hassfest Passing:** Run `hassfest` to ensure the `manifest.json` and integration structure comply with core requirements.
- [ ] **HACS Action Passing:** Use the HACS validate GitHub action to ensure there are no structural issues.
- [ ] **Fix Tests:** HACS reviewers look favorably upon integrations with passing tests. Fix the 247 failing `pytest` errors before submission.

### 4. Release Management
- [ ] **Changelog:** Move away from maintaining a massive `CHANGELOG.md` file manually, and instead use GitHub Releases with automated release notes. HACS surfaces GitHub Releases directly in the UI.

### 5. The Pull Request
- [ ] Once the above is complete, open a PR to `hacs/default` repository. Expect the review process to take 2-4 weeks. Be prepared to address reviewer feedback promptly.
