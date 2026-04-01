export interface Robot {
  id: string
  external_identifier: string
  name: string | null
  description: string | null
  status: 'pending_approval' | 'approved' | 'rejected' | 'disabled'
  user_id: number | null
}
