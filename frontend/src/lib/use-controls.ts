/** Hooks de datos de controles (TanStack Query, D70). Toda mutación refresca la lista al terminar. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type Control, type ControlInput, type ControlPatch } from "./api";

const CONTROLS_KEY = ["controls"] as const;
type ControlsData = { items: Control[]; count: number };

export function useControls() {
  return useQuery({ queryKey: CONTROLS_KEY, queryFn: api.listControls });
}

export function useCreateControl() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: ControlInput) => api.createControl(input),
    onSettled: () => qc.invalidateQueries({ queryKey: CONTROLS_KEY }),
  });
}

/**
 * Edición con actualización OPTIMISTA: el cambio se ve al instante en la tabla y,
 * si la API falla, se vuelve al estado anterior.
 */
export function useUpdateControl() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: ControlPatch }) => api.updateControl(id, patch),
    onMutate: async ({ id, patch }) => {
      await qc.cancelQueries({ queryKey: CONTROLS_KEY });
      const previous = qc.getQueryData<ControlsData>(CONTROLS_KEY);
      qc.setQueryData<ControlsData>(CONTROLS_KEY, (old) =>
        old && { ...old, items: old.items.map((c) => (c.id === id ? { ...c, ...patch } : c)) },
      );
      return { previous };
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) qc.setQueryData(CONTROLS_KEY, context.previous);
    },
    onSettled: () => qc.invalidateQueries({ queryKey: CONTROLS_KEY }),
  });
}

export function useDeleteControl() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.deleteControl(id),
    onSettled: () => qc.invalidateQueries({ queryKey: CONTROLS_KEY }),
  });
}

/**
 * Un control por id. Si la lista ya está en la caché, se usa ese dato de inmediato (sin request);
 * si se entra por un link directo (/app/controles/<id>/editar), se pide GET /controls/{id}.
 */
export function useControl(id: string | undefined) {
  const qc = useQueryClient();
  return useQuery({
    queryKey: ["controls", id],
    queryFn: async () => (await api.getControl(id!)).item,
    enabled: Boolean(id),
    initialData: () => qc.getQueryData<ControlsData>(CONTROLS_KEY)?.items.find((c) => c.id === id),
  });
}
