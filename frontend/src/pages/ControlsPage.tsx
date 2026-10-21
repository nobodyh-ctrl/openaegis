import { useMemo, useState } from "react";
import { useCollection } from "@cloudscape-design/collection-hooks";
import Box from "@cloudscape-design/components/box";
import Button from "@cloudscape-design/components/button";
import ContentLayout from "@cloudscape-design/components/content-layout";
import ButtonDropdown from "@cloudscape-design/components/button-dropdown";
import Header from "@cloudscape-design/components/header";
import Link from "@cloudscape-design/components/link";
import Pagination from "@cloudscape-design/components/pagination";
import Select, { type SelectProps } from "@cloudscape-design/components/select";
import SpaceBetween from "@cloudscape-design/components/space-between";
import Table, { type TableProps } from "@cloudscape-design/components/table";
import TextFilter from "@cloudscape-design/components/text-filter";
import { useNavigate, useSearchParams } from "react-router";
import { ControlDetails } from "@/components/controls/ControlDetails";
import { DeleteControlModal } from "@/components/controls/DeleteControlModal";
import { SEVERITY_ORDER, SeverityBadge, StatusBadge, severityLabel, statusLabel } from "@/components/controls/badges";
import { useSplitPanel } from "@/components/layout/split-panel";
import { SEVERITIES, STATUSES, type Control, type Status } from "@/lib/api";
import { useFollow } from "@/lib/navigation";
import { useNotifications } from "@/lib/notifications";
import { useControls, useUpdateControl } from "@/lib/use-controls";

const ALL: SelectProps.Option = { value: "ALL", label: "Toda severidad" };
const ALL_STATUS: SelectProps.Option = { value: "ALL", label: "Todo estado" };
const severityOptions = [ALL, ...SEVERITIES.map((s) => ({ value: s, label: severityLabel(s) }))];
const statusOptions = [ALL_STATUS, ...STATUSES.map((s) => ({ value: s, label: statusLabel(s) }))];
const relative = new Intl.RelativeTimeFormat("es", { numeric: "auto" });

function timeAgo(iso: string) {
  const minutes = Math.round((new Date(iso).getTime() - Date.now()) / 60000);
  if (Math.abs(minutes) < 60) return relative.format(minutes, "minute");
  const hours = Math.round(minutes / 60);
  if (Math.abs(hours) < 24) return relative.format(hours, "hour");
  return relative.format(Math.round(hours / 24), "day");
}

export function ControlsPage() {
  const { data, isPending, error, refetch, isFetching } = useControls();
  const update = useUpdateControl();
  const { notify } = useNotifications();
  const navigate = useNavigate();
  const follow = useFollow();

  // Filtros iniciales desde la URL (links del Dashboard: ?estado=FAIL, ?severidad=HIGH)
  const [params] = useSearchParams();
  const [severity, setSeverity] = useState(() => severityOptions.find((o) => o.value === params.get("severidad")) ?? ALL);
  const [status, setStatus] = useState(() => statusOptions.find((o) => o.value === params.get("estado")) ?? ALL_STATUS);
  const [deleting, setDeleting] = useState<Control | null>(null);

  const columns = useMemo<TableProps.ColumnDefinition<Control>[]>(() => [
    {
      id: "code",
      header: "Código",
      cell: (c) => <Link href={`/app/controles/${c.id}/editar`} onFollow={follow}>{c.code}</Link>,
      sortingField: "code",
      width: 130,
    },
    // Texto escrito por usuarios: React lo escapa (sin dangerouslySetInnerHTML), protección contra XSS
    { id: "title", header: "Control", cell: (c) => c.title, sortingField: "title", minWidth: 220 },
    { id: "service", header: "Servicio", cell: (c) => c.service, sortingField: "service", width: 120 },
    { id: "category", header: "Categoría", cell: (c) => c.category, sortingField: "category", width: 170 },
    {
      id: "severity",
      header: "Severidad",
      cell: (c) => <SeverityBadge severity={c.severity} />,
      sortingComparator: (a, b) => SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity],
      width: 120,
    },
    { id: "status", header: "Estado", cell: (c) => <StatusBadge status={c.status} />, sortingField: "status", width: 140 },
    { id: "updated", header: "Actualizado", cell: (c) => timeAgo(c.updated_at), sortingField: "updated_at", width: 140 },
  ], [follow]);

  // Filtros, orden y paginación en el cliente (D72)
  const { items, collectionProps, filterProps, paginationProps, filteredItemsCount, actions } = useCollection(data?.items ?? [], {
    filtering: {
      filteringFunction: (c, text) => {
        const q = text.trim().toLowerCase();
        return (severity.value === "ALL" || c.severity === severity.value)
          && (status.value === "ALL" || c.status === status.value)
          && (!q || [c.code, c.title, c.service, c.category].some((t) => t.toLowerCase().includes(q)));
      },
      empty: (
        <Box textAlign="center" color="inherit" padding="l">
          <SpaceBetween size="xs">
            <b>Todavía no hay controles</b>
            <Box variant="p" color="inherit">Creá el primero para armar tu checklist de seguridad.</Box>
            <Button href="/app/controles/nuevo" onFollow={follow}>Nuevo control</Button>
          </SpaceBetween>
        </Box>
      ),
      noMatch: (
        <Box textAlign="center" color="inherit" padding="l">
          <SpaceBetween size="xs">
            <b>Ningún control coincide con los filtros</b>
            <Button onClick={() => { actions.setFiltering(""); setSeverity(ALL); setStatus(ALL_STATUS); }}>Limpiar filtros</Button>
          </SpaceBetween>
        </Box>
      ),
    },
    sorting: { defaultState: { sortingColumn: columns[4] } },
    pagination: { pageSize: 20 },
    selection: { keepSelection: false, trackBy: "id" },
  });

  const selectedId = collectionProps.selectedItems?.[0]?.id;
  // El seleccionado se toma de los datos frescos (cambia en el panel al editar el estado)
  const selected = data?.items.find((c) => c.id === selectedId);

  const changeStatus = (control: Control, newStatus: Status) => {
    if (control.status === newStatus) return;
    update.mutate(
      { id: control.id, patch: { status: newStatus } },
      {
        onSuccess: () => notify("success", `${control.code}: ${statusLabel(newStatus)}.`),
        onError: (err) => notify("error", `No se pudo cambiar el estado: ${err.message}`),
      },
    );
  };

  const details = useMemo(() => selected ? (
    <ControlDetails
      control={selected}
      onEdit={() => navigate(`/app/controles/${selected.id}/editar`)}
      onDelete={() => setDeleting(selected)}
      onChangeStatus={(s) => changeStatus(selected, s)}
    />
  ) : null, [selected]); // solo cambia cuando cambia el control seleccionado (o sus datos)
  useSplitPanel(details);

  return (
    <ContentLayout
      header={
        <Header variant="h1" description="Reglas de seguridad de tu cuenta. Seleccioná un control para ver su detalle.">
          Controles
        </Header>
      }
    >
      <Table
        {...collectionProps}
        variant="container"
        selectionType="single"
        trackBy="id"
        resizableColumns
        columnDefinitions={columns}
        items={items}
        loading={isPending}
        loadingText="Cargando controles"
        ariaLabels={{ itemSelectionLabel: (_, c) => `Seleccionar ${c.code}`, selectionGroupLabel: "Selección de controles" }}
        header={
          <Header
            variant="h2"
            counter={data ? (filteredItemsCount === data.count ? `(${data.count})` : `(${filteredItemsCount}/${data.count})`) : undefined}
            description="Cada control es una regla que se evalúa en la cuenta."
            actions={
              <SpaceBetween direction="horizontal" size="xs">
                <Button iconName="refresh" ariaLabel="Actualizar" loading={isFetching && !isPending} onClick={() => void refetch()} />
                <ButtonDropdown
                  disabled={!selected}
                  items={[
                    { id: "edit", text: "Editar", iconName: "edit" },
                    { id: "status", text: "Cambiar estado", items: STATUSES.map((s) => ({ id: `status:${s}`, text: statusLabel(s), disabled: selected?.status === s })) },
                    { id: "delete", text: "Eliminar", iconName: "remove" },
                  ]}
                  onItemClick={({ detail }) => {
                    if (!selected) return;
                    if (detail.id === "edit") navigate(`/app/controles/${selected.id}/editar`);
                    else if (detail.id === "delete") setDeleting(selected);
                    else if (detail.id.startsWith("status:")) changeStatus(selected, detail.id.slice(7) as Status);
                  }}
                >
                  Acciones
                </ButtonDropdown>
                <Button variant="primary" iconName="add-plus" href="/app/controles/nuevo" onFollow={follow}>Nuevo control</Button>
              </SpaceBetween>
            }
          >
            Todos los controles
          </Header>
        }
        filter={
          <SpaceBetween direction="horizontal" size="xs">
            <div style={{ minWidth: 280 }}>
              <TextFilter {...filterProps} filteringPlaceholder="Buscar por código, título, servicio o categoría" filteringAriaLabel="Buscar controles" countText={`${filteredItemsCount ?? 0} coincidencias`} />
            </div>
            <Select selectedOption={severity} onChange={({ detail }) => setSeverity(detail.selectedOption)} options={severityOptions} ariaLabel="Filtrar por severidad" />
            <Select selectedOption={status} onChange={({ detail }) => setStatus(detail.selectedOption)} options={statusOptions} ariaLabel="Filtrar por estado" />
          </SpaceBetween>
        }
        pagination={<Pagination {...paginationProps} />}
        empty={error ? (
          <Box textAlign="center" color="inherit" padding="l">
            <SpaceBetween size="xs">
              <b>No se pudieron cargar los controles</b>
              <Box variant="p" color="inherit">{error.message}</Box>
              <Button onClick={() => void refetch()}>Reintentar</Button>
            </SpaceBetween>
          </Box>
        ) : collectionProps.empty}
      />

      <DeleteControlModal control={deleting} onDismiss={() => { setDeleting(null); actions.setSelectedItems([]); }} />
    </ContentLayout>
  );
}
