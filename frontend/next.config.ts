import type { NextConfig } from "next";

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const apiConnectSource = apiBaseUrl.startsWith("/") ? "" : new URL(apiBaseUrl).origin;
const backendOrigin = process.env.AGENTSPROUT_BACKEND_ORIGIN?.replace(/\/$/, "");
if (backendOrigin && process.env.NODE_ENV === "production" && !backendOrigin.startsWith("https://")) {
  throw new Error("Production AGENTSPROUT_BACKEND_ORIGIN must use HTTPS");
}
const isProduction = process.env.NODE_ENV === "production";
const contentSecurityPolicy = [
  "default-src 'self'",
  `connect-src 'self'${apiConnectSource ? ` ${apiConnectSource}` : ""}`,
  "font-src 'self' data:",
  "frame-ancestors 'none'",
  "img-src 'self' data:",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  `script-src 'self' 'unsafe-inline'${isProduction ? "" : " 'unsafe-eval'"}`,
  "style-src 'self' 'unsafe-inline'",
].join("; ");

const nextConfig: NextConfig = {
  async rewrites() {
    if (!backendOrigin) return [];
    return [
      {
        source: "/api-proxy/:path*",
        destination: `${backendOrigin}/:path*`,
      },
    ];
  },
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "Content-Security-Policy", value: contentSecurityPolicy },
          { key: "Permissions-Policy", value: "camera=(), geolocation=(), microphone=()" },
          { key: "Referrer-Policy", value: "no-referrer" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
        ],
      },
    ];
  },
};

export default nextConfig;
