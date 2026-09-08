import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

/**
 * Inject a Content-Security-Policy into the built index.html.
 *
 * This is the control that actually addresses the "one injected script
 * exfiltrates both tokens" threat. Moving tokens into HttpOnly cookies does
 * not: it requires a same-site deployment to be safe, and it re-introduces an
 * ambient credential (and with it CSRF) on the refresh endpoint. A CSP blocks
 * the exfiltration step regardless of where the tokens live, and blocks the
 * injection step for most XSS classes outright.
 *
 * Build-only on purpose — the dev server needs inline and eval'd script for
 * HMR, so shipping one policy for both would either break `npm run dev` or
 * water the production policy down to nothing.
 *
 * A meta tag is used so the policy travels with the artifact and does not
 * depend on host configuration. If you deploy behind a CDN or proxy that can
 * set response headers, prefer the real header — a meta tag cannot express
 * `frame-ancestors`, `report-uri` or `sandbox`, and the browser logs a console
 * warning for each one it has to ignore. `frame-ancestors 'none'` is therefore
 * set on the host instead (`vercel.json`, alongside `X-Frame-Options: DENY`)
 * and deliberately left out of the list below — keep it that way.
 */
function cspPlugin(apiOrigin) {
  const directives = [
    "default-src 'self'",
    // No 'unsafe-inline' and no 'unsafe-eval': Vite emits real script files
    // for production builds, so nothing here needs either.
    "script-src 'self'",
    // Tailwind compiles to a stylesheet. 'unsafe-inline' is still required
    // for style *attributes*, which this app uses heavily via the `t` prop
    // (style={{...}}). That is a genuine weakening of the style channel and
    // nothing more: it does not permit script execution.
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data:",
    "font-src 'self' data:",
    // The API origin has to be reachable; everything else is refused, which
    // is what stops a compromised dependency POSTing tokens elsewhere.
    `connect-src 'self' ${apiOrigin}`.trim(),
    "object-src 'none'",
    "base-uri 'none'",
    "form-action 'self'",
    // No `frame-ancestors` here: it is ignored in a meta-delivered policy and
    // only produces a console warning. Clickjacking is covered by the host's
    // response headers (see vercel.json).
  ]

  // Only when the API is already on TLS: this directive rewrites http:// to
  // https://, which would break a build previewed against a local backend.
  if (apiOrigin.startsWith('https://') || !apiOrigin) {
    directives.push('upgrade-insecure-requests')
  }

  const policy = directives.join('; ')

  return {
    name: 'clearspend-csp',
    apply: 'build',
    transformIndexHtml(html) {
      return {
        html,
        tags: [
          {
            tag: 'meta',
            attrs: { 'http-equiv': 'Content-Security-Policy', content: policy },
            injectTo: 'head-prepend',
          },
        ],
      }
    },
  }
}

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, import.meta.dirname, '')
  const apiBase = env.VITE_API_BASE_URL || 'http://localhost:8000/api'

  let apiOrigin = ''
  try {
    const { origin } = new URL(apiBase)
    // An opaque origin stringifies to the literal "null", which is not a
    // valid CSP source expression — emitting it produces a policy the
    // browser parses but that protects nothing extra, with no error shown.
    // Reachable in practice: some shells rewrite a leading-slash value into
    // a filesystem path (Git Bash turns `/api` into `C:/…/api`), whose
    // `c:` scheme has no tuple origin.
    apiOrigin = origin === 'null' ? '' : origin
  } catch {
    // Relative base (same-origin API behind a path rewrite) — 'self' covers it.
  }

  return {
    plugins: [
      react(),
      tailwindcss(),
      cspPlugin(apiOrigin),
    ],
  }
})
