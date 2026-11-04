import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  skipTrailingSlashRedirect: true,
  // Same-origin cookies and CSRF also work when Django runs behind a tunnel.
  async rewrites() {
    const upstream = process.env.API_UPSTREAM_ORIGIN;
    if (!upstream) return [];
    const origin = new URL(upstream);
    if (origin.protocol !== "https:" || origin.pathname !== "/") {
      throw new Error("API_UPSTREAM_ORIGIN must be an HTTPS origin without a path");
    }
    // Django routes end in '/'; omitting it here causes an APPEND_SLASH loop.
    return [{ source: "/api/:path*", destination: `${origin.origin}/api/:path*/` }];
  },
};

export default nextConfig;
