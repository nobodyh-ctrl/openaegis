import Box from "@cloudscape-design/components/box";
import Button from "@cloudscape-design/components/button";
import ButtonDropdown from "@cloudscape-design/components/button-dropdown";
import ColumnLayout from "@cloudscape-design/components/column-layout";
import KeyValuePairs from "@cloudscape-design/components/key-value-pairs";
import SpaceBetween from "@cloudscape-design/components/space-between";
import SplitPanel from "@cloudscape-design/components/split-panel";
import { STATUSES, type Control, type Status } from "@/lib/api";
import { SeverityBadge, StatusBadge, statusLabel } from "./badges";

const dateFormat = new Intl.DateTimeFormat("es-AR", { dateStyle: "medium", timeStyle: "short" });

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
          <ButtonDropdown
            items={STATUSES.map((s) => ({ id: s, text: statusLabel(s), disabled: control.status === s }))}
            onItemClick={({ detail }) => onChangeStatus(detail.id as Status)}
          >
            Cambiar estado
          </ButtonDropdown>
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
      </SpaceBetween>
    </SplitPanel>
  );
}
