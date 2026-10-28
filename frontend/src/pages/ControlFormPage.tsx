import { useEffect, useState } from "react";
import Box from "@cloudscape-design/components/box";
import Button from "@cloudscape-design/components/button";
import ColumnLayout from "@cloudscape-design/components/column-layout";
import Container from "@cloudscape-design/components/container";
import Form from "@cloudscape-design/components/form";
import FormField from "@cloudscape-design/components/form-field";
import Header from "@cloudscape-design/components/header";
import Input from "@cloudscape-design/components/input";
import SegmentedControl from "@cloudscape-design/components/segmented-control";
import Select from "@cloudscape-design/components/select";
import SpaceBetween from "@cloudscape-design/components/space-between";
import Spinner from "@cloudscape-design/components/spinner";
import Textarea from "@cloudscape-design/components/textarea";
import Tiles from "@cloudscape-design/components/tiles";
import { useNavigate, useParams } from "react-router";
import { SeverityBadge, StatusBadge, statusLabel } from "@/components/controls/badges";
import { ApiError, CHECK_IDS, SEVERITIES, STATUSES, type Control, type ControlInput, type ControlPatch } from "@/lib/api";
import { CHECK_INFO } from "@/lib/checks";
import {
  EMPTY_FORM, FIELD_RULES, toControlInput, validateControlForm,
  type ControlFormValues, type FieldName, type FormErrors,
} from "@/lib/control-rules";
import { useNotifications } from "@/lib/notifications";
import { useControl, useCreateControl, useUpdateControl } from "@/lib/use-controls";

const MANUAL_OPTION = { value: "", label: "Manual", description: "El estado lo definís vos." };
const EVALUATION_OPTIONS = [
  MANUAL_OPTION,
  ...CHECK_IDS.map((id) => ({ value: id, label: CHECK_INFO[id].label, description: CHECK_INFO[id].description })),
];

const SEVERITY_HELP: Record<string, string> = {
  CRITICAL: "Exposición directa o compromiso de la cuenta.",
  HIGH: "Riesgo importante que hay que resolver pronto.",
  MEDIUM: "Debilidad a planificar.",
  LOW: "Buena práctica o mejora menor.",
};

function toFormValues(control?: Control): ControlFormValues {
  if (!control) return EMPTY_FORM;
  return {
    code: control.code, title: control.title, service: control.service, category: control.category,
    severity: control.severity, status: control.status,
    description: control.description ?? "", remediation: control.remediation ?? "",
    check_id: control.check_id ?? "",
  };
}

/** Alta (/app/controles/nuevo) y edición (/app/controles/:id/editar) en página completa, como en la consola. */
export function ControlFormPage() {
  const { id } = useParams();
  const isEdit = Boolean(id);
  const { data: control, isPending: loadingControl, error: loadError } = useControl(id);

  if (isEdit && loadingControl) return <Box textAlign="center" padding="xxl"><Spinner size="large" /></Box>;
  if (isEdit && (loadError || !control)) {
    return (
      <Container header={<Header variant="h1">Control no encontrado</Header>}>
        <Box variant="p">{loadError?.message ?? "El control no existe."}</Box>
      </Container>
    );
  }
  return <ControlForm key={control?.id ?? "nuevo"} control={control} />;
}

function ControlForm({ control }: { control?: Control }) {
  const isEdit = Boolean(control);
  const navigate = useNavigate();
  const { notify } = useNotifications();
  const create = useCreateControl();
  const update = useUpdateControl();
  const [values, setValues] = useState<ControlFormValues>(() => toFormValues(control));
  const [errors, setErrors] = useState<FormErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const saving = create.isPending || update.isPending;
  const automatic = Boolean(values.check_id);

  useEffect(() => { document.title = `${isEdit ? `Editar ${control?.code}` : "Nuevo control"} · OpenAegis`; }, [isEdit, control]);

  const set = (field: FieldName, value: string) => {
    setValues((v) => ({ ...v, [field]: value }));
    setErrors((e) => ({ ...e, [field]: undefined }));
  };

  async function submit() {
    setFormError(null);
    const found = validateControlForm(values);
    setErrors(found);
    if (Object.keys(found).length > 0) return;
    let sent: ControlPatch | ControlInput = {};
    try {
      if (control) {
        // PATCH solo con los campos que cambiaron (D73)
        const original = toFormValues(control);
        const patch: ControlPatch = {};
        for (const field of Object.keys(values) as FieldName[]) {
          // En un control automático el status no se manda: lo pone el scanner (la API respondería 409)
          if (field === "status" && automatic) continue;
          const value = values[field].trim();
          if (value !== original[field].trim()) (patch as Record<string, string>)[field] = value;
        }
        sent = patch;
        if (Object.keys(patch).length > 0) {
          await update.mutateAsync({ id: control.id, patch });
          notify("success", `Control ${values.code.trim()} actualizado.`);
        }
      } else {
        const input = toControlInput(values);
        sent = input;
        const { item } = await create.mutateAsync(input);
        notify("success", `Control ${item.code} creado.`);
      }
      navigate("/app/controles");
    } catch (err) {
      // El backend tiene la última palabra. Un 409 con el código en el body es un código repetido:
      // va al campo. Cualquier otro error (incluido el 409 de un control automático), arriba de los botones.
      if (err instanceof ApiError && err.status === 409 && "code" in sent) setErrors((e) => ({ ...e, code: err.message }));
      else setFormError(err instanceof Error ? err.message : "Error inesperado.");
    }
  }

  const text = (name: FieldName, opts: { placeholder?: string; multiline?: boolean; description?: string } = {}) => (
    <FormField
      label={FIELD_RULES[name].label}
      description={opts.description}
      info={FIELD_RULES[name].required ? undefined : <Box variant="small" color="text-body-secondary">opcional</Box>}
      constraintText={FIELD_RULES[name].maxLength ? `${values[name].length}/${FIELD_RULES[name].maxLength} caracteres` : undefined}
      errorText={errors[name]}
      stretch
    >
      {opts.multiline ? (
        <Textarea value={values[name]} onChange={({ detail }) => set(name, detail.value)} rows={4} placeholder={opts.placeholder} invalid={Boolean(errors[name])} />
      ) : (
        <Input value={values[name]} onChange={({ detail }) => set(name, detail.value)} placeholder={opts.placeholder} invalid={Boolean(errors[name])} />
      )}
    </FormField>
  );

  return (
    <form onSubmit={(e) => { e.preventDefault(); void submit(); }} noValidate>
      <Form
        header={
          <Header variant="h1" description={isEdit ? "Solo se envían los campos que cambies." : "Definí una regla de seguridad para evaluar en la cuenta."}>
            {isEdit ? `Editar ${control?.code}` : "Nuevo control"}
          </Header>
        }
        actions={
          <SpaceBetween direction="horizontal" size="xs">
            <Button formAction="none" variant="link" onClick={() => navigate("/app/controles")}>Cancelar</Button>
            <Button variant="primary" loading={saving}>{isEdit ? "Guardar cambios" : "Crear control"}</Button>
          </SpaceBetween>
        }
        errorText={formError ?? undefined}
      >
        <SpaceBetween size="l">
          <Container header={<Header variant="h2" description="Cómo se identifica el control.">Identificación</Header>}>
            <SpaceBetween size="m">
              <ColumnLayout columns={2}>
                {text("code", { placeholder: "S3-001", description: "Único entre todos los controles." })}
                {text("title", { placeholder: "S3 Block Public Access" })}
              </ColumnLayout>
              <ColumnLayout columns={2}>
                {text("service", { placeholder: "S3" })}
                {text("category", { placeholder: "Data protection" })}
              </ColumnLayout>
            </SpaceBetween>
          </Container>

          <Container header={<Header variant="h2" description="Qué tan grave es y en qué estado está hoy.">Evaluación</Header>}>
            <SpaceBetween size="l">
              <FormField label="Severidad" errorText={errors.severity} stretch>
                <Tiles
                  value={values.severity || null}
                  onChange={({ detail }) => set("severity", detail.value)}
                  columns={4}
                  items={SEVERITIES.map((s) => ({ value: s, label: <SeverityBadge severity={s} />, description: SEVERITY_HELP[s] }))}
                />
              </FormField>
              <FormField
                label={FIELD_RULES.check_id.label}
                description="Un control automático lo evalúa un check de solo lectura en cada scan."
                errorText={errors.check_id}
                stretch
              >
                <Select
                  selectedOption={EVALUATION_OPTIONS.find((o) => o.value === values.check_id) ?? MANUAL_OPTION}
                  onChange={({ detail }) => set("check_id", detail.selectedOption.value ?? "")}
                  options={EVALUATION_OPTIONS}
                  invalid={Boolean(errors.check_id)}
                />
              </FormField>
              {automatic ? (
                <FormField label="Estado" description="Lo define el scanner con los findings del último scan. Para cambiarlo a mano, pasá el control a Manual.">
                  {control?.check_id ? <StatusBadge status={control.status} /> : <Box color="text-body-secondary">Pendiente del primer scan.</Box>}
                </FormField>
              ) : (
                <FormField label="Estado">
                  <SegmentedControl
                    selectedId={values.status}
                    onChange={({ detail }) => set("status", detail.selectedId)}
                    label="Estado"
                    options={STATUSES.map((s) => ({ id: s, text: statusLabel(s) }))}
                  />
                </FormField>
              )}
            </SpaceBetween>
          </Container>

          <Container header={<Header variant="h2" description="Contexto para quien tenga que resolverlo.">Detalle</Header>}>
            <SpaceBetween size="m">
              {text("description", { multiline: true, placeholder: "Qué verifica este control y por qué importa." })}
              {text("remediation", { multiline: true, placeholder: "Cómo corregirlo si no cumple." })}
            </SpaceBetween>
          </Container>
        </SpaceBetween>
      </Form>
    </form>
  );
}
