/**
 * Ghostline Official Site Configuration
 * Single source of truth for release artifacts, versions, and repository links.
 */

export const siteConfig = {
  version: "1.0.7",
  releaseTag: "v1.0.7",
  releaseDate: "2026-11-08",
  repoUrl: "https://github.com/Mohammed-Ayyan/GhostLine",
  releaseUrl: "https://github.com/Mohammed-Ayyan/GhostLine/releases/tag/v1.0.7",
  latestReleaseApi: "https://api.github.com/repos/Mohammed-Ayyan/GhostLine/releases/latest",
  downloads: {
    installer: {
      name: "Ghostline-Setup.exe",
      url: "https://github.com/Mohammed-Ayyan/GhostLine/releases/latest/download/Ghostline-Setup.exe",
      sizeMb: 245.59,
      sha256: "e93dce81cae1bc993db3b87d3aa5cfdbb4135875ceb2a3d10edc5ab451ec61c6",
      description: "Standard self-contained Windows installer (Recommended)"
    },
    portable: {
      name: "Ghostline-Portable.zip",
      url: "https://github.com/Mohammed-Ayyan/GhostLine/releases/latest/download/Ghostline-Portable.zip",
      sizeMb: 312.18,
      sha256: "fe108324b7f4932b9ceb0a34144df08121a1a3b952c328f233c1de86ed279acc",
      description: "Standalone zero-install portable archive"
    },
    checksums: {
      name: "SHA256SUMS.txt",
      url: "https://github.com/Mohammed-Ayyan/GhostLine/releases/latest/download/SHA256SUMS.txt"
    }
  },
  systemRequirements: {
    os: "Windows 10 (1903+) or Windows 11 64-bit",
    ram: "8 GB RAM (16 GB recommended for local 7B models)",
    gpu: "Optional (CUDA/DirectML supported via Ollama)",
    storage: "1.5 GB disk space (+ model files)"
  }
};
