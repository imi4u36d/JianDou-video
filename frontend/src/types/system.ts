export interface SystemInfo {
  chip: string
  cpu_cores: number
  gpu_cores: number
  ram_gb: number
  ram_free_gb: number
  tier: 'low' | 'medium' | 'high' | 'ultra'
  max_resolution: [number, number]
  max_frames: number
  supports_fp16: boolean
  supports_audio: boolean
  ffmpeg_available: boolean
  macos_version: string
  mlx_version: string
}
