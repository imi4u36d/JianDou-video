export interface ModelEntry {
  name: string
  repo: string
  filename: string
  local_path: string
  size_bytes: number
  version: string
  model_type: string
  downloaded: boolean
  downloaded_at: string | null
  sha256: string | null
}

export interface ModelDownloadProgress {
  name: string
  progress: number
  downloaded_bytes: number
  total_bytes: number
  speed_mbps: number
  eta_seconds: number | null
}
