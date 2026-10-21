import Box from "@cloudscape-design/components/box";
import Button from "@cloudscape-design/components/button";
import Modal from "@cloudscape-design/components/modal";
import SpaceBetween from "@cloudscape-design/components/space-between";
import type { Control } from "@/lib/api";
import { useNotifications } from "@/lib/notifications";
import { useDeleteControl } from "@/lib/use-controls";

/** Confirmación de borrado (D53: borrado real). */
export function DeleteControlModal({ control, onDismiss }: { control: Control | null; onDismiss: () => void }) {
  const remove = useDeleteControl();
  const { notify } = useNotifications();

  async function confirm() {
    if (!control) return;
    try {
      await remove.mutateAsync(control.id);
      notify("success", `Control ${control.code} eliminado.`);
    } catch (err) {
      notify("error", err instanceof Error ? err.message : "No se pudo eliminar el control.");
    }
    onDismiss();
  }

  return (
    <Modal
      visible={control !== null}
      onDismiss={onDismiss}
      header={`¿Eliminar ${control?.code ?? ""}?`}
      footer={
        <Box float="right">
          <SpaceBetween direction="horizontal" size="xs">
            <Button variant="link" onClick={onDismiss}>Cancelar</Button>
            <Button variant="primary" loading={remove.isPending} onClick={() => void confirm()}>Eliminar</Button>
          </SpaceBetween>
        </Box>
      }
    >
      Se va a borrar <b>{control?.title}</b>. Esta acción no se puede deshacer.
    </Modal>
  );
}
