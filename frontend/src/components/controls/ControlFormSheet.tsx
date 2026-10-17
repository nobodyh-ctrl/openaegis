import { useEffect, useState, type FormEvent } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Sheet, SheetContent, SheetDescription, SheetFooter, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Textarea } from "@/components/ui/textarea";
import { ApiError, SEVERITIES, STATUSES, type Control, type ControlPatch, type Severity, type Status } from "@/lib/api";
import {
  EMPTY_FORM, FIELD_RULES, toControlInput, validateControlForm,
  type ControlFormValues, type FieldName, type FormErrors,
} from "@/lib/control-rules";
import { useCreateControl, useUpdateControl } from "@/lib/use-controls";
import { severityLabel, statusLabel } from "./badges";

function toFormValues(control?: Control): ControlFormValues {
  if (!control) return EMPTY_FORM;
  return {
    code: control.code, title: control.title, service: control.service, category: control.category,
    severity: control.severity, status: control.status,
    description: control.description ?? "", remediation: control.remediation ?? "",
  };
}

/** Panel lateral para crear (sin `control`) o editar (con `control`). */
export function ControlFormSheet({ open, onOpenChange, control }: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  control?: Control;
}) {
  const isEdit = Boolean(control);
  const [values, setValues] = useState<ControlFormValues>(() => toFormValues(control));
  const [errors, setErrors] = useState<FormErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const create = useCreateControl();
  const update = useUpdateControl();
  const saving = create.isPending || update.isPending;

  // Cada vez que se abre, se carga el control elegido (o el formulario vacío).
  useEffect(() => {
    if (open) {
      setValues(toFormValues(control));
      setErrors({});
      setFormError(null);
    }
  }, [open, control]);

  const set = (field: FieldName, value: string) => {
    setValues((v) => ({ ...v, [field]: value }));
    setErrors((e) => ({ ...e, [field]: undefined }));
  };

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setFormError(null);
    const found = validateControlForm(values);
    setErrors(found);
    if (Object.keys(found).length > 0) return;

    try {
      if (control) {
        // PATCH solo con los campos que cambiaron
        const original = toFormValues(control);
        const patch: ControlPatch = {};
        for (const field of Object.keys(values) as FieldName[]) {
          const value = values[field].trim();
          if (value !== original[field].trim()) (patch as Record<string, string>)[field] = value;
        }
        if (Object.keys(patch).length === 0) return onOpenChange(false);
        await update.mutateAsync({ id: control.id, patch });
        toast.success(`Control ${values.code.trim()} actualizado`);
      } else {
        const { item } = await create.mutateAsync(toControlInput(values));
        toast.success(`Control ${item.code} creado`);
      }
      onOpenChange(false);
    } catch (err) {
      // El backend tiene la última palabra: un 409 es del código; un 400, un dato inválido
      if (err instanceof ApiError && err.status === 409) setErrors((e) => ({ ...e, code: err.message }));
      else setFormError(err instanceof Error ? err.message : "Error inesperado.");
    }
  }

  const field = (name: FieldName, input: React.ReactNode) => (
    <div className="grid gap-1.5">
      <Label htmlFor={name}>
        {FIELD_RULES[name].label}
        {FIELD_RULES[name].required && <span className="text-destructive" aria-hidden="true">*</span>}
      </Label>
      {input}
      {errors[name] && <p id={`${name}-error`} className="text-xs text-destructive">{errors[name]}</p>}
    </div>
  );

  const textProps = (name: FieldName) => ({
    id: name,
    value: values[name],
    maxLength: FIELD_RULES[name].maxLength,
    onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => set(name, e.target.value),
    "aria-invalid": Boolean(errors[name]),
    "aria-describedby": errors[name] ? `${name}-error` : undefined,
  });

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-lg">
        <form onSubmit={handleSubmit} noValidate className="flex h-full flex-col">
          <SheetHeader>
            <SheetTitle>{isEdit ? `Editar ${control?.code}` : "Nuevo control"}</SheetTitle>
            <SheetDescription>
              {isEdit ? "Solo se envían los campos que cambies." : "Los campos con * son obligatorios."}
            </SheetDescription>
          </SheetHeader>

          <div className="grid gap-4 px-4">
            <div className="grid grid-cols-2 gap-4">
              {field("code", <Input {...textProps("code")} placeholder="S3-001" className="font-mono" />)}
              {field("service", <Input {...textProps("service")} placeholder="S3" />)}
            </div>
            {field("title", <Input {...textProps("title")} placeholder="S3 Block Public Access" />)}
            {field("category", <Input {...textProps("category")} placeholder="Data protection" />)}
            <div className="grid grid-cols-2 gap-4">
              {field("severity",
                <Select value={values.severity} onValueChange={(v) => set("severity", v)}>
                  <SelectTrigger id="severity" className="w-full" aria-invalid={Boolean(errors.severity)}>
                    <SelectValue placeholder="Elegí una" />
                  </SelectTrigger>
                  <SelectContent>
                    {SEVERITIES.map((s) => <SelectItem key={s} value={s}>{severityLabel(s as Severity)}</SelectItem>)}
                  </SelectContent>
                </Select>,
              )}
              {field("status",
                <Select value={values.status} onValueChange={(v) => set("status", v)}>
                  <SelectTrigger id="status" className="w-full"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {STATUSES.map((s) => <SelectItem key={s} value={s}>{statusLabel(s as Status)}</SelectItem>)}
                  </SelectContent>
                </Select>,
              )}
            </div>
            {field("description", <Textarea {...textProps("description")} rows={3} />)}
            {field("remediation", <Textarea {...textProps("remediation")} rows={3} />)}
            {formError && (
              <p role="alert" className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
                {formError}
              </p>
            )}
          </div>

          <SheetFooter className="mt-auto">
            <Button type="submit" disabled={saving}>{saving ? "Guardando…" : isEdit ? "Guardar cambios" : "Crear control"}</Button>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Cancelar</Button>
          </SheetFooter>
        </form>
      </SheetContent>
    </Sheet>
  );
}
