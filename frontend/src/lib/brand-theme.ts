import { applyTheme } from "@cloudscape-design/components/theming";

/**
 * Identidad visual de OpenAegis sobre Cloudscape (D76): la paleta original (azul marino con tinte
 * y teal) aplicada a los tokens de la consola. Cada token define su valor en claro y en oscuro.
 */
const TEAL = { light: "#0f766e", dark: "#2dd4bf" };
const TEAL_HOVER = { light: "#115e59", dark: "#5eead4" };
const TEAL_ACTIVE = { light: "#134e4a", dark: "#99f6e4" };

export function applyBrandTheme() {
  applyTheme({
    theme: {
      tokens: {
        // Acento
        colorBackgroundButtonPrimaryDefault: TEAL,
        colorBackgroundButtonPrimaryHover: TEAL_HOVER,
        colorBackgroundButtonPrimaryActive: TEAL_ACTIVE,
        colorBorderButtonPrimaryDefault: TEAL,
        colorTextButtonPrimaryDefault: { light: "#ffffff", dark: "#042f2e" },
        colorTextButtonPrimaryHover: { light: "#ffffff", dark: "#042f2e" },
        colorTextButtonNormalDefault: TEAL,
        colorTextButtonNormalHover: TEAL_HOVER,
        colorBorderButtonNormalHover: TEAL_HOVER,
        colorTextLinkDefault: TEAL,
        colorTextLinkHover: TEAL_HOVER,
        colorTextAccent: TEAL,
        colorBorderItemFocused: TEAL,
        colorBackgroundControlChecked: TEAL,
        colorBackgroundProgressBarValueDefault: TEAL,
        colorBackgroundItemSelected: { light: "#ecfdf9", dark: "#0f2a2a" },
        colorBorderItemSelected: TEAL,
        colorBackgroundSegmentActive: TEAL,
        colorTextSegmentActive: { light: "#ffffff", dark: "#042f2e" },
        // Superficies: azul marino con tinte (oscuro) y gris azulado (claro)
        colorBackgroundLayoutMain: { light: "#f4f7f9", dark: "#0b1118" },
        colorBackgroundLayoutPanelContent: { light: "#f2f6f7", dark: "#0e151d" },
        colorBackgroundContainerContent: { light: "#ffffff", dark: "#111a24" },
        colorBackgroundContainerHeader: { light: "#ffffff", dark: "#111a24" },
        colorBackgroundInputDefault: { light: "#ffffff", dark: "#0e151d" },
        colorBackgroundDropdownItemDefault: { light: "#ffffff", dark: "#111a24" },
        colorBackgroundCellShaded: { light: "#f2f6f7", dark: "#0e151d" },
        colorBorderDividerDefault: { light: "#c8d3d8", dark: "#223040" },
        colorBorderDividerSecondary: { light: "#dde5e9", dark: "#1a2532" },
        colorBorderContainerTop: { light: "#c8d3d8", dark: "#223040" },
        colorBorderInputDefault: { light: "#aebbc2", dark: "#2c3a4a" },
      },
      contexts: {
        // La barra superior siempre con el fondo de la marca
        "top-navigation": {
          tokens: {
            colorBackgroundContainerContent: "#0b1524",
            colorTextAccent: "#2dd4bf",
          },
        },
      },
    },
  });
}
