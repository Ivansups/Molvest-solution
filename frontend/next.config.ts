import type { NextConfig } from "next";

function getBackendBaseUrl(): string {
  return (process.env.API_INTERNAL_URL ?? "http://127.0.0.1:8000").replace(
    /\/$/,
    "",
  );
}

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/backend/:path*",
        destination: `${getBackendBaseUrl()}/:path*`,
      },
    ];
  },
};

export default nextConfig;
