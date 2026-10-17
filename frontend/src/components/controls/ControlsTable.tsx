import { MoreHorizontal, Pencil, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuRadioGroup,
  DropdownMenuRadioItem, DropdownMenuSeparator, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { STATUSES, type Control, type Status } from "@/lib/api";
import { useUpdateControl } from "@/lib/use-controls";
import { SeverityBadge, StatusBadge, statusLabel } from "./badges";

const dateFormat = new Intl.DateTimeFormat("es-AR", { dateStyle: "medium", timeStyle: "short" });

/** Cambio de estado desde la tabla, con actualización optimista (useUpdateControl). */
function StatusMenu({ control }: { control: Control }) {
  const update = useUpdateControl();
  const change = (status: string) => {
    if (status === control.status) return;
    update.mutate(
      { id: control.id, patch: { status: status as Status } },
      {
        onSuccess: () => toast.success(`${control.code}: ${statusLabel(status as Status)}`),
        onError: (err) => toast.error(`No se pudo cambiar el estado: ${err.message}`),
      },
    );
  };
  return (
    <DropdownMenu>
      <DropdownMenuTrigger className="rounded-md outline-none focus-visible:ring-2 focus-visible:ring-ring" aria-label={`Cambiar estado de ${control.code}`}>
        <StatusBadge status={control.status} />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start">
        <DropdownMenuLabel>Estado</DropdownMenuLabel>
        <DropdownMenuRadioGroup value={control.status} onValueChange={change}>
          {STATUSES.map((s) => (
            <DropdownMenuRadioItem key={s} value={s}>{statusLabel(s)}</DropdownMenuRadioItem>
          ))}
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

export function ControlsTable({ controls, onEdit, onDelete }: {
  controls: Control[];
  onEdit: (control: Control) => void;
  onDelete: (control: Control) => void;
}) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="hidden w-28 sm:table-cell">Código</TableHead>
          <TableHead>Control</TableHead>
          <TableHead className="hidden w-32 sm:table-cell">Severidad</TableHead>
          <TableHead className="w-36">Estado</TableHead>
          <TableHead className="hidden w-44 lg:table-cell">Actualizado</TableHead>
          <TableHead className="w-12"><span className="sr-only">Acciones</span></TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {controls.map((c) => (
          <TableRow key={c.id}>
            <TableCell className="hidden font-mono text-xs sm:table-cell">{c.code}</TableCell>
            <TableCell className="max-w-0 whitespace-normal">
              {/* Texto escrito por usuarios: React lo escapa (sin dangerouslySetInnerHTML), protección contra XSS */}
              <p className="font-mono text-xs text-muted-foreground sm:hidden">{c.code}</p>
              <p className="truncate font-medium">{c.title}</p>
              <p className="truncate text-xs text-muted-foreground">{c.service} · {c.category}</p>
              <div className="mt-1 sm:hidden"><SeverityBadge severity={c.severity} /></div>
            </TableCell>
            <TableCell className="hidden sm:table-cell"><SeverityBadge severity={c.severity} /></TableCell>
            <TableCell><StatusMenu control={c} /></TableCell>
            <TableCell className="hidden text-xs text-muted-foreground lg:table-cell">
              {dateFormat.format(new Date(c.updated_at))}
            </TableCell>
            <TableCell>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" size="icon-sm" aria-label={`Acciones de ${c.code}`}><MoreHorizontal /></Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem onSelect={() => onEdit(c)}><Pencil /> Editar</DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem variant="destructive" onSelect={() => onDelete(c)}><Trash2 /> Eliminar</DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
