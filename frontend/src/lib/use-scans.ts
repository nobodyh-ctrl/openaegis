/** Hooks de scans y findings (TanStack Query, D70). */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError, type Scan } from "./api";

const LATEST_SCAN_KEY = ["scans", "latest"] as const;
const findingsKey = (controlId: string) => ["findings", controlId] as const;

const POLL_EVERY_MS = 2000;
const POLL_TIMEOUT_MS = 60000;

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

export function useLatestScan() {
  return useQuery({ queryKey: LATEST_SCAN_KEY, queryFn: async () => (await api.latestScan()).item });
}

/** Findings de un control automático (el panel de detalle solo lo usa si el control tiene check_id). */
export function useFindings(controlId: string) {
  return useQuery({
    queryKey: findingsKey(controlId),
    queryFn: async () => (await api.listFindings(controlId)).items,
  });
}

/**
 * Dispara un scan y ESPERA a que termine (D93: el POST responde 202 sin esperar).
 * Sabe que terminó cuando cambia el started_at del último scan. Compara dos datos del SERVIDOR:
 * si comparara contra la hora del navegador, un reloj desfasado rompería la espera.
 */
export function useStartScan() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (): Promise<Scan> => {
      const before = (await api.latestScan()).item?.started_at;
      await api.startScan();

      const deadline = Date.now() + POLL_TIMEOUT_MS;
      while (Date.now() < deadline) {
        await sleep(POLL_EVERY_MS);
        const latest = (await api.latestScan()).item;
        if (latest && latest.started_at !== before) return latest;
      }
      // status 0 = no es un error HTTP; el scan puede seguir corriendo y terminar más tarde
      throw new ApiError(0, "El scan no terminó en 60 segundos. Revisá el resultado en unos minutos.");
    },
    onSuccess: (scan) => qc.setQueryData(LATEST_SCAN_KEY, scan),
    // El scan cambió el status de los controles automáticos y sus findings: hay que volver a pedirlos
    onSettled: () => Promise.all([
      qc.invalidateQueries({ queryKey: ["controls"] }),
      qc.invalidateQueries({ queryKey: ["findings"] }),
      qc.invalidateQueries({ queryKey: LATEST_SCAN_KEY }),
    ]),
  });
}
