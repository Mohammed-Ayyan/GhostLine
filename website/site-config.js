/**
 * Ghostline Official Site Configuration
 * Single source of truth for release artifacts, versions, and repository links.
 */

export const siteConfig = {
  version: "1.0.3",
  releaseTag: "v1.0.3",
  releaseDate: "2026-11-08",
  repoUrl: "https://github.com/Mohammed-Ayyan/GhostLine",
  releaseUrl: "https://github.com/Mohammed-Ayyan/GhostLine/releases/tag/v1.0.3",
  latestReleaseApi: "https://api.github.com/repos/Mohammed-Ayyan/GhostLine/releases/latest",
  downloads: {
    installer: {
      name: "Ghostline-Setup.exe",
      url: "https://github.com/Mohammed-Ayyan/GhostLine/releases/download/v1.0.3/Ghostline-Setup.exe",
      sizeMb: 245.35,
      sha256: "642fd709c1d5e59ec1207f03fbf619faf10eff0adc2cada691e66c2ea6c83f4d",
      description: "Standard self-contained Windows installer (Recommended)"
    },
    portable: {
      name: "Ghostline-Portable.zip",
      url: "https://github.com/Mohammed-Ayyan/GhostLine/releases/download/v1.0.3/Ghostline-Portable.zip",
      sizeMb: 311.94,
      sha256: "6e4a69ee690408065c58b5c792c2572be8b00ce2275c430fb6203e6e3ce5c103",
      description: "Standalone zero-install portable archive"
    },
    checksums: {
      name: "SHA256SUMS.txt",
      url: "https://github.com/Mohammed-Ayyan/GhostLine/releases/download/v1.0.3/SHA256SUMS.txt"
    }
  },
  systemRequirements: {
    os: "Windows 10 (1903+) or Windows 11 64-bit",
    ram: "8 GB RAM (16 GB recommended for local 7B models)",
    gpu: "Optional (CUDA/DirectML supported via Ollama)",
    storage: "1.5 GB disk space (+ model files)"
  }
};
