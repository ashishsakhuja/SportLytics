const nextConfig = {
  async redirects() {
    return [
      {
        source: "/:path*",
        has: [
          {
            type: "host",
            value: "sportlytics.net",
          },
        ],
        destination: "https://www.sportlytics.net/:path*",
        permanent: true,
      },
    ];
  },
};

export default nextConfig;