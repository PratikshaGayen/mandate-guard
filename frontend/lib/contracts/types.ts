/**
 * TypeScript types for the MandateGuard contract
 */

export interface TransactionReceipt {
  status: string;
  hash: string;
  blockNumber?: number;
  [key: string]: any;
}

export interface Mandate {
  id: string;
  text: string;
  principal: string;
  operator: string;
  bond_wei: number | string;
  spend_ceiling_wei: number | string;
  challenge_window_seconds: number | string;
  created_at: number | string;
  bond_intact: boolean;
}

export interface ChallengeSummary {
  id: string;
  challenger: string;
  deposit_wei: number | string;
  opened_at: number | string;
  state: string;
}

export interface Action {
  id: string;
  mandate_id: string;
  merchant_url: string;
  item: string;
  price: string;
  purchased_at: string;
  recorded_at: number | string;
  challenge_closes_at: number | string;
  open_challenge_id: string;
  state: string;
  challenge?: ChallengeSummary;
}

export interface Payout {
  recipient: string;
  amount_wei: number | string;
  purpose: string;
}

export interface Challenge {
  id: string;
  action_id: string;
  mandate_id: string;
  challenger: string;
  deposit_wei: number | string;
  opened_at: number | string;
  state: string;
  verdict_within_mandate: boolean;
  verdict_clause_violated: string;
  verdict_severity: number | string;
  verdict_reasoning: string;
  resolved_at: number | string;
  payouts: Payout[];
}
