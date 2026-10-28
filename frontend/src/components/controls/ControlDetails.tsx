import Box from "@cloudscape-design/components/box";
import Button from "@cloudscape-design/components/button";
import ButtonDropdown from "@cloudscape-design/components/button-dropdown";
import ColumnLayout from "@cloudscape-design/components/column-layout";
import Header from "@cloudscape-design/components/header";
import KeyValuePairs from "@cloudscape-design/components/key-value-pairs";
import SpaceBetween from "@cloudscape-design/components/space-between";
import SplitPanel from "@cloudscape-design/components/split-panel";
import Table from "@cloudscape-design/components/table";
import { STATUSES, type Control, type Finding, type Status } from "@/lib/api";
import { checkLabel } from "@/lib/checks";
import { useFindings } from "@/lib/use-scans";
import { EvaluationBadge, FindingBadge, SeverityBadge, StatusBadge, statusLabel } from "./badges";

const dateFormat = new Intl.DateTimeFormat("es-AR", { dateStyle: "medium", timeStyle: "short" });

/** Nombre legible del recurso: el bucket sin el prefijo del ARN, o la cuenta / el root. */
function resourceLabel(resourceId: string) {
  if (resourceId === "account") return "Cuenta";
  if (resourceId === "root") return "Usuario root";
  if (resourceId === "check") return "(el check no se pudo correr)";
  return resourceId.replace(/^arn:aws:s3:::/, "");
}

/** Findings del último scan: un resultado por recurso evaluado. */
function Findings({ controlId }: { controlId: string }) {
  const { data, isPending, error } = useFindings(controlId);
  const evaluatedAt = data?.[0]?.evaluated_at;
  return (
    <Table<Finding>
      variant="embedded"
      header={
        <Header
          variant="h3"
          counter={data ? `(${data.length})` : undefined}
          description={evaluatedAt ? `Último scan: ${dateFormat.format(new Date(evaluatedAt))}` : undefined}
        >
          Findings
        </Header>
      }
      items={data ?? []}
      loading={isPending}
      loadingText="Cargando findings"
      trackBy="resource_id"
      columnDefinitions={[
        { id: "status", header: "Resultado", cell: (f) => <FindingBadge status={f.status} />, width: 170 },
        { id: "resource", header: "Recurso", cell: (f) => resourceLabel(f.resource_id), width: 220 },
        { id: "evidence", header: "Evidencia", cell: (f) => f.evidence },
      ]}
      wrapLines
      empty={
        <Box textAlign="center" color="inherit" padding="s">
          {error ? `No se pudieron cargar: ${error.message}` : "Todavía no hay findings. Corré un scan desde el Dashboard."}
        </Box>
      }
    />
  );
}

/** Panel de detalle del control seleccionado (como el de EC2 en la consola). */
export function ControlDetails({ control, onEdit, onDelete, onChangeStatus }: {
  control: Control;
  onEdit: () => void;
  onDelete: () => void;
  onChangeStatus: (status: Status) => void;
}) {
  return (
    <SplitPanel
      header={`${control.code} · ${control.title}`}
      closeBehavior="collapse"
      i18nStrings={{ preferencesTitle: "Preferencias del panel", preferencesPositionLabel: "Posición", preferencesPositionDescription: "Elegí dónde se muestra el panel.", preferencesPositionSide: "Al costado", preferencesPositionBottom: "Abajo", preferencesConfirm: "Aceptar", preferencesCancel: "Cancelar", closeButtonAriaLabel: "Cerrar panel", openButtonAriaLabel: "Abrir panel", resizeHandleAriaLabel: "Cambiar tamaño del panel" }}
    >
      <SpaceBetween size="l">
        <SpaceBetween direction="horizontal" size="xs">
          <Button iconName="edit" onClick={onEdit}>Editar</Button>
          {/* En un control automático el estado lo pone el scanner: no se ofrece cambiarlo a mano */}
          {!control.check_id && (
            <ButtonDropdown
              items={STATUSES.map((s) => ({ id: s, text: statusLabel(s), disabled: control.status === s }))}
              onItemClick={({ detail }) => onChangeStatus(detail.id as Status)}
            >
              Cambiar estado
            </ButtonDropdown>
          )}
          <Button iconName="remove" onClick={onDelete}>Eliminar</Button>
        </SpaceBetween>

        <KeyValuePairs
          columns={4}
          items={[
            { label: "Código", value: <Box variant="code">{control.code}</Box> },
            { label: "Servicio", value: control.service },
            { label: "Categoría", value: control.category },
            { label: "Severidad", value: <SeverityBadge severity={control.severity} /> },
            { label: "Estado", value: <StatusBadge status={control.status} /> },
            {
              label: "Evaluación",
              value: control.check_id
                ? <SpaceBetween direction="horizontal" size="xs"><EvaluationBadge checkId={control.check_id} />{checkLabel(control.check_id)}</SpaceBetween>
                : <EvaluationBadge />,
            },
            { label: "Creado", value: dateFormat.format(new Date(control.created_at)) },
            { label: "Actualizado", value: dateFormat.format(new Date(control.updated_at)) },
            { label: "ID", value: <Box variant="code" fontSize="body-s">{control.id}</Box> },
          ]}
        />

        <ColumnLayout columns={2} variant="text-grid">
          <div>
            <Box variant="awsui-key-label">Descripción</Box>
            <Box variant="p">{control.description || <Box color="text-status-inactive">Sin descripción.</Box>}</Box>
          </div>
          <div>
            <Box variant="awsui-key-label">Remediación</Box>
            <Box variant="p">{control.remediation || <Box color="text-status-inactive">Sin remediación cargada.</Box>}</Box>
          </div>
        </ColumnLayout>

        {/* key: al cambiar de control, la tabla arranca de cero (sin los findings del anterior) */}
        {control.check_id && <Findings key={control.id} controlId={control.id} />}
      </SpaceBetween>
    </SplitPanel>
  );
}
