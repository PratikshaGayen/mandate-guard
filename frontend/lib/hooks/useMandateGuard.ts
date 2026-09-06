"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useMemo } from "react";
import MandateGuard from "../contracts/MandateGuard";
import { getContractAddress, getStudioUrl } from "../genlayer/client";
import type { FeePresetLevel } from "../genlayer/fees";
import { useWallet } from "../genlayer/wallet";
import type {
  Action,
  Challenge,
  Mandate,
} from "../contracts/types";

/**
 * Hook to get the MandateGuard contract instance.
 * Returns null if the contract address is not configured.
 */
export function useMandateGuardContract(): MandateGuard | null {
  const { address } = useWallet();
  const contractAddress = getContractAddress();
  const studioUrl = getStudioUrl();

  return useMemo(() => {
    if (!contractAddress) {
      return null;
    }
    return new MandateGuard(contractAddress, address, studioUrl);
  }, [contractAddress, address, studioUrl]);
}

/** The operator's mandates. */
export function useMandates() {
  const contract = useMandateGuardContract();
  const { address } = useWallet();

  return useQuery<Mandate[], Error>({
    queryKey: ["mandates", address],
    queryFn: async () => {
      if (!contract || !address) {
        return [];
      }
      const ids = await contract.getMandateIdsByOperator(address);
      return Promise.all(ids.map((id) => contract.getMandate(id)));
    },
    enabled: !!contract && !!address,
  });
}

/** One mandate with its full action feed (D10: elapsed-ness is derived in the UI). */
export function useMandateActions(mandateId: string | null) {
  const contract = useMandateGuardContract();

  return useQuery<Action[], Error>({
    queryKey: ["actions", mandateId],
    queryFn: async () => {
      if (!contract || !mandateId) {
        return [];
      }
      const ids = await contract.getActionIdsByMandate(mandateId);
      return Promise.all(ids.map((id) => contract.getAction(id)));
    },
    enabled: !!contract && !!mandateId,
    refetchInterval: 15000,
  });
}

/** One challenge, verdict and payouts included (D12). */
export function useChallenge(challengeId: string | null) {
  const contract = useMandateGuardContract();

  return useQuery<Challenge | null, Error>({
    queryKey: ["challenge", challengeId],
    queryFn: async () => {
      if (!contract || !challengeId) {
        return null;
      }
      return contract.getChallenge(challengeId);
    },
    enabled: !!contract && !!challengeId,
    refetchInterval: 15000,
  });
}

/** The exact deposit the contract requires for challenging an action (D3). */
export function useRequiredDeposit(actionId: string | null) {
  const contract = useMandateGuardContract();

  return useQuery<bigint | null, Error>({
    queryKey: ["requiredDeposit", actionId],
    queryFn: async () => {
      if (!contract || !actionId) {
        return null;
      }
      return contract.requiredDeposit(actionId);
    },
    enabled: !!contract && !!actionId,
  });
}

export function useRegisterMandate() {
  const contract = useMandateGuardContract();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      text,
      principal,
      spendCeilingWei,
      challengeWindowSeconds,
      feePresetLevel,
    }: {
      text: string;
      principal: string;
      spendCeilingWei: string;
      challengeWindowSeconds: string;
      feePresetLevel?: FeePresetLevel;
    }) => {
      if (!contract) {
        throw new Error("Contract not configured");
      }
      const feePreset = await contract.estimateFees(
        "register_mandate",
        [text, principal, BigInt(spendCeilingWei), BigInt(challengeWindowSeconds)],
        feePresetLevel
      );
      return contract.registerMandate(
        text,
        principal,
        spendCeilingWei,
        challengeWindowSeconds,
        feePreset
      );
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["mandates"] });
    },
  });
}

export function useRecordAction() {
  const contract = useMandateGuardContract();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      mandateId,
      merchantUrl,
      item,
      price,
      purchasedAt,
      feePresetLevel,
    }: {
      mandateId: string;
      merchantUrl: string;
      item: string;
      price: string;
      purchasedAt: string;
      feePresetLevel?: FeePresetLevel;
    }) => {
      if (!contract) {
        throw new Error("Contract not configured");
      }
      const feePreset = await contract.estimateFees(
        "record_action",
        [mandateId, merchantUrl, item, price, purchasedAt],
        feePresetLevel
      );
      return contract.recordAction(
        mandateId,
        merchantUrl,
        item,
        price,
        purchasedAt,
        feePreset
      );
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["actions", variables.mandateId] });
    },
  });
}

export function useChallengeAction() {
  const contract = useMandateGuardContract();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      actionId,
      depositWei,
      feePresetLevel,
    }: {
      actionId: string;
      depositWei: string;
      feePresetLevel?: FeePresetLevel;
    }) => {
      if (!contract) {
        throw new Error("Contract not configured");
      }
      const feePreset = await contract.estimateFees(
        "challenge",
        [actionId],
        feePresetLevel
      );
      return contract.challenge(actionId, depositWei, feePreset);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["actions"] });
      queryClient.invalidateQueries({ queryKey: ["challenge"] });
    },
  });
}

export function useResolveChallenge() {
  const contract = useMandateGuardContract();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      challengeId,
      feePresetLevel,
    }: {
      challengeId: string;
      feePresetLevel?: FeePresetLevel;
    }) => {
      if (!contract) {
        throw new Error("Contract not configured");
      }
      const feePreset = await contract.estimateFees(
        "resolve",
        [challengeId],
        feePresetLevel
      );
      return contract.resolve(challengeId, feePreset);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["actions"] });
      queryClient.invalidateQueries({ queryKey: ["challenge"] });
      queryClient.invalidateQueries({ queryKey: ["mandates"] });
    },
  });
}
