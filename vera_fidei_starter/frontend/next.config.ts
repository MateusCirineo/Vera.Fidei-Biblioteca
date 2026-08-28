import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "img.cancaonova.com",
        port: "",
        pathname: "/cnimages/canais/uploads/sites/**",
      },
      {
        protocol: "https",
        hostname: "www.vaticannews.va",
        port: "",
        pathname: "/content/dam/vaticannews/**",
      },
    ],
  },
  webpack: (config) => {
    config.resolve.alias = {
      ...config.resolve.alias,
      canvas: false,
    };
    return config;
  },
};

export default nextConfig;
