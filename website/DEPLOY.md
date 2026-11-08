# Deploying Ghostline Website to Vercel

The `website/` directory is a 100% pure static web application (HTML5, Fluent 2 CSS, and ES Modules) with zero build steps or runtime dependencies.

---

## Option 1: One-Click Deploy via Vercel Web Dashboard (Recommended)

1. Push your changes to your GitHub repository:
   ```bash
   git push origin main
   ```
2. Navigate to [vercel.com](https://vercel.com) and log in.
3. Click **"Add New..."** &rarr; **"Project"**.
4. Import your **GhostLine** GitHub repository.
5. In **Root Directory**, click **Edit** and select:
   ```
   website
   ```
6. Under **Build and Output Settings**:
   - **Framework Preset**: *Other*
   - **Build Command**: *Leave blank*
   - **Output Directory**: *Leave blank* (or `.`)
7. Click **"Deploy"**.

Your website will be live in ~15 seconds with global CDN caching, SSL certificates, and clean URLs automatically configured via `vercel.json`!

---

## Option 2: Deploy via Vercel CLI

If you have Node.js and the Vercel CLI installed:

```bash
# 1. Navigate to the website directory
cd website

# 2. Deploy preview
npx vercel

# 3. Deploy to production
npx vercel --prod
```

---

## Verification Checklist

After deploying, verify:
- [ ] Root `/` renders the homepage and interactive simulated demo.
- [ ] Clean URLs work: `/install`, `/models`, `/use`, `/privacy`, `/faq`, `/changelog`, `/responsible-use`.
- [ ] `/download` automatically redirects to the latest GitHub release.
- [ ] Copy buttons on code blocks function properly.
- [ ] Hardware sliders on `/models` dynamically update recommended model badges.
- [ ] No mixed content or CSP errors in browser DevTools console.
