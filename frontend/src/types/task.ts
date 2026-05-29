export interface Task {
  id: string
  mode: 't2v' | 'i2v' | 'fflf' | 'extend' | 'a2v'
  status: 'pending' | 'running' | 'done' | 'failed' | 'cancelled'
  priority: number

  prompt: string
  negative_prompt: string
  image_path: string | null
  audio_path: string | null

  duration: number
  width: number
  height: number
  fps: number
  steps: number
  cfg: number
  seed: number
  preset: string

  model_version: string
  pipeline: string
  fp16: boolean
  low_memory: boolean

  upscale: string
  upscale_factor: number
  generate_audio: boolean
  audio_prompt: string

  output_path: string | null
  preview_path: string | null

  created_at: string
  started_at: string | null
  completed_at: string | null
  progress: number
  stage: string
  current_step: number
  total_steps: number
  eta_seconds: number | null
  error_message: string | null
}
