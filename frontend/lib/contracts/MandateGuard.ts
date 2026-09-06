import { createClient } from "genlayer-js";
import { studionet } from "genlayer-js/chains";
import type { Mandate, Action, Challenge, TransactionReceipt } from "./types";
import {
  estimateWriteFeePreset,
  feePresetToTransactionFees,
  type FeePresetEstimate,
  type FeePresetLevel,
} from "../genlayer/fees";

/**
 * MandateGuard contract class for interacting with the Mandate Guard
 * Intelligent Contract. Bindings cover every method the UI needs; the exact
 * challenge deposit is READ from the contract (required_deposit), never
 * computed client-side.
 */
class MandateGuard {
  private contractAddress: `0x${string}`;
  private client: any;
  private studioUrl?: string;

  constructor(
    contractAddress: string,
    address?: string | null,
    studioUrl?: string
  ) {
    this.contractAddress = contractAddress as `0x${string}`;
    this.studioUrl = studioUrl;

    const config: any = {
      chain: studionet,
    };

    if (address) {
      config.account = address as `0x${string}`;
    }

    if (studioUrl) {
      config.endpoint = studioUrl;
    }

    this.client = createClient(config);
  }

  updateAccount(address: string): void {
    const config: any = {
      chain: studionet,
      account: address as `0x${string}`,
    };

    if (this.studioUrl) {
      config.endpoint = this.studioUrl;
    }

    this.client = createClient(config);
  }

  private async read(functionName: string, args: any[]): Promise<any> {
    return await this.client.readContract({
      address: this.contractAddress,
      functionName,
      args,
    });
  }

  private async write(
    functionName: string,
    args: any[],
    value: bigint,
    feePreset?: FeePresetEstimate
  ): Promise<TransactionReceipt> {
    const fees = feePresetToTransactionFees(feePreset);
    const txHash = await this.client.writeContract({
      address: this.contractAddress,
      functionName,
      args,
      value,
      ...(fees ? { fees } : {}),
    });

    const receipt = await this.client.waitForTransactionReceipt({
      hash: txHash,
      status: "ACCEPTED" as any,
      retries: 24,
      interval: 5000,
    });

    return receipt as TransactionReceipt;
  }

  async estimateFees(
    functionName: string,
    args: any[],
    level: FeePresetLevel = "standard"
  ): Promise<FeePresetEstimate | undefined> {
    return estimateWriteFeePreset(
      this.client,
      {
        address: this.contractAddress,
        functionName,
        args,
      },
      level,
    );
  }

  // ── Views ────────────────────────────────────────────────────────────────

  async getMandate(mandateId: string): Promise<Mandate> {
    return (await this.read("get_mandate", [mandateId])) as Mandate;
  }

  async getMandateIdsByOperator(operator: string): Promise<string[]> {
    return (await this.read("get_mandate_ids_by_operator", [operator])) as string[];
  }

  async getActionIdsByMandate(mandateId: string): Promise<string[]> {
    return (await this.read("get_action_ids_by_mandate", [mandateId])) as string[];
  }

  async getAction(actionId: string): Promise<Action> {
    return (await this.read("get_action", [actionId])) as Action;
  }

  async getChallenge(challengeId: string): Promise<Challenge> {
    return (await this.read("get_challenge", [challengeId])) as Challenge;
  }

  /** The exact deposit a challenge requires, read from the contract (D3). */
  async requiredDeposit(actionId: string): Promise<bigint> {
    const wei = await this.read("required_deposit", [actionId]);
    return BigInt(wei);
  }

  // ── Writes ───────────────────────────────────────────────────────────────

  /**
   * Register a mandate. Payable: the operator bond arrives with this call (D2/D7).
   */
  async registerMandate(
    text: string,
    principal: string,
    spendCeilingWei: string,
    challengeWindowSeconds: string,
    feePreset?: FeePresetEstimate
  ): Promise<TransactionReceipt> {
    return await this.write(
      "register_mandate",
      [text, principal, BigInt(spendCeilingWei), BigInt(challengeWindowSeconds)],
      BigInt(spendCeilingWei),
      feePreset
    );
  }

  async recordAction(
    mandateId: string,
    merchantUrl: string,
    item: string,
    price: string,
    purchasedAt: string,
    feePreset?: FeePresetEstimate
  ): Promise<TransactionReceipt> {
    return await this.write(
      "record_action",
      [mandateId, merchantUrl, item, price, purchasedAt],
      BigInt(0),
      feePreset
    );
  }

  async challenge(
    actionId: string,
    depositWei: string,
    feePreset?: FeePresetEstimate
  ): Promise<TransactionReceipt> {
    return await this.write(
      "challenge",
      [actionId],
      BigInt(depositWei),
      feePreset
    );
  }

  /**
   * Permissionless settlement crank (D14). Waits for the transaction to be
   * accepted; the emitted payouts execute on finalization shortly after.
   */
  async resolve(challengeId: string, feePreset?: FeePresetEstimate): Promise<TransactionReceipt> {
    return await this.write("resolve", [challengeId], BigInt(0), feePreset);
  }
}

export default MandateGuard;
