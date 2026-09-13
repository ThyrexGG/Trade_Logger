import { apiDelete, apiGet, apiPost } from './client'

export type AccountRowCounts = Record<string, number>

interface ListAccountsResponse {
  accounts: Record<string, AccountRowCounts>
}

interface ExportAccountResponse {
  account_id: string
  export_path: string
}

interface RemoveAccountResponse {
  account_id: string
  deleted_rows: Record<string, number>
}

export interface ExportSnapshot {
  export_path: string
  account_id: string
  exported_at: string | null
  row_counts: AccountRowCounts
}

interface ListExportsResponse {
  exports: ExportSnapshot[]
}

interface RestoreAccountResponse {
  restored_rows: Record<string, number>
}

/** Row counts per account_id, per table -- what's actually in the journal/analytics DB for this user. */
export function listAccounts(signal?: AbortSignal): Promise<ListAccountsResponse> {
  return apiGet<ListAccountsResponse>('/api/accounts', { signal })
}

/** Read-only. Writes a full snapshot of this account's rows to disk on the server and returns its path. */
export function exportAccount(accountId: string): Promise<ExportAccountResponse> {
  return apiPost<ExportAccountResponse>(`/api/accounts/${encodeURIComponent(accountId)}/export`, {})
}

/** Deletes every row for this account_id. Requires the export_path from exportAccount() for this exact account_id. */
export function removeAccount(accountId: string, exportedFilePath: string): Promise<RemoveAccountResponse> {
  return apiDelete<RemoveAccountResponse>(
    `/api/accounts/${encodeURIComponent(accountId)}?exported_file_path=${encodeURIComponent(exportedFilePath)}`,
  )
}

/** Snapshots on disk this caller could restore, newest first -- optionally filtered to one account_id. */
export function listExports(accountId?: string, signal?: AbortSignal): Promise<ListExportsResponse> {
  const qs = accountId ? `?account_id=${encodeURIComponent(accountId)}` : ''
  return apiGet<ListExportsResponse>(`/api/accounts/exports${qs}`, { signal })
}

/** Replays a snapshot back into the database. Additive only -- rows that already exist (by primary key) are left alone. */
export function restoreAccount(exportedFilePath: string): Promise<RestoreAccountResponse> {
  return apiPost<RestoreAccountResponse>(
    `/api/accounts/restore?exported_file_path=${encodeURIComponent(exportedFilePath)}`,
    {},
  )
}
