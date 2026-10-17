import { toast } from "sonner";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription,
  AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import type { Control } from "@/lib/api";
import { useDeleteControl } from "@/lib/use-controls";

/** Confirmación de borrado (D53: borrado real). */
export function DeleteControlDialog({ control, onClose }: { control: Control | null; onClose: () => void }) {
  const remove = useDeleteControl();

  async function confirm() {
    if (!control) return;
    try {
      await remove.mutateAsync(control.id);
      toast.success(`Control ${control.code} eliminado`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "No se pudo eliminar el control.");
    }
    onClose();
  }

  return (
    <AlertDialog open={control !== null} onOpenChange={(open) => !open && onClose()}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>¿Eliminar {control?.code}?</AlertDialogTitle>
          <AlertDialogDescription>
            Se va a borrar "{control?.title}". Esta acción no se puede deshacer.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancelar</AlertDialogCancel>
          <AlertDialogAction onClick={confirm} disabled={remove.isPending} className="bg-destructive text-white hover:bg-destructive/90">
            Eliminar
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
