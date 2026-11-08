/**
 * Ghostline Official Site Configuration
 * Single source of truth for release artifacts, versions, and repository links.
 */

export const siteConfig = {
  version: "1.0.2",
  releaseTag: "v1.0.2",
  releaseDate: "2026-11-08",
  repoUrl: "https://github.com/Mohammed-Ayyan/GhostLine",
  releaseUrl: "https://github.com/Mohammed-Ayyan/GhostLine/releases/tag/v1.0.2",
  latestReleaseApi: "https://api.github.com/repos/Mohammed-Ayyan/GhostLine/releases/latest",
  downloads: {
    installer: {
      name: "Ghostline-Setup.exe",
      url: "https://github.com/Mohammed-Ayyan/GhostLine/releases/download/v1.0.2/Ghostline-Setup.exe",
      sizeMb: 245.35,
      sha256: "9a7fbd067bb09ea23603f6f85becc13d817da5bffd7c6e701f6093223bce5f9f",
      description: "Standard self-contained Windows installer (Recommended)"
    },
    portable: {
      name: "Ghostline-Portable.zip",
      url: "https://github.com/Mohammed-Ayyan/GhostLine/releases/download/v1.0.2/Ghostline-Portable.zip",
      sizeMb: 311.93,
      sha256: "dd85d0b8751b0f982ed76c3c4ded0d1ee4f6ea6fa52da297637b90085032adda",
      description: "Standalone zero-install portable archive"
    },
    checksums: {
      name: "SHA256SUMS.txt",
      url: "https://github.com/Mohammed-Ayyan/GhostLine/releases/download/v1.0.2/SHA256SUMS.txt"
    }
  },
  systemRequirements: {
    os: "Windows 10 (1903+) or Windows 11 64-bit",
    ram: "8 GB RAM (16 GB recommended for local 7B models)",
    gpu: "Optional (CUDA/DirectML supported via Ollama)",
    storage: "1.5 GB disk space (+ model files)"
  }
};
