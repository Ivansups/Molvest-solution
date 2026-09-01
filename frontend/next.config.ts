import type { NextConfig } from "next";
import { getApiBaseUrl } from "./src/lib/api-base";

const backendBaseUrl = getApiBaseUrl();

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/backend/:path*",
        destination: `${backendBaseUrl}/:path*`,
      },
    ];
  },
};

export default nextConfig;
