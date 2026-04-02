import { createContext, useEffect, useState } from "react";
import {
  DockviewReact,
  DockviewDefaultTab,
  type DockviewApi,
  type DockviewReadyEvent,
  type IDockviewPanelHeaderProps,
} from "dockview";
import {
  FluentProvider,
  Toaster,
  useId,
  useToastController,
  Menu,
  MenuTrigger,
  MenuPopover,
  MenuList,
  MenuItemRadio,
  Button,
  makeStyles,
  tokens,
  type MenuProps,
} from "@fluentui/react-components";
import {
  WeatherMoonRegular,
  WeatherSunnyRegular,
  DesktopRegular,
} from "@fluentui/react-icons";
import { panelComponents } from "./panels";
import { useTheme, type ThemeMode } from "./hooks/useTheme";

export const DockviewApiContext = createContext<DockviewApi | null>(null);
export const ToasterContext = createContext<ReturnType<
  typeof useToastController
> | null>(null);

const LAYOUT_KEY = "cpf_dockview_layout_v2";

// Tab component that hides close button for permanent panels
function PermanentTab(props: IDockviewPanelHeaderProps) {
  return <DockviewDefaultTab {...props} hideClose={true} />;
}

function ClosableTab(props: IDockviewPanelHeaderProps) {
  return <DockviewDefaultTab {...props} hideClose={false} />;
}

const tabComponents = {
  permanent: PermanentTab,
  closable: ClosableTab,
};

const useStyles = makeStyles({
  themeButton: {
    position: "fixed",
    bottom: "12px",
    right: "12px",
    zIndex: 100,
    minWidth: "auto",
    backgroundColor: tokens.colorNeutralBackground1,
    boxShadow: tokens.shadow8,
    borderRadius: "50%",
    width: "36px",
    height: "36px",
  },
});

function ThemeIcon({ mode, isDark }: { mode: ThemeMode; isDark: boolean }) {
  if (mode === "system")
    return <DesktopRegular style={{ width: 18, height: 18 }} />;
  if (isDark)
    return <WeatherMoonRegular style={{ width: 18, height: 18 }} />;
  return <WeatherSunnyRegular style={{ width: 18, height: 18 }} />;
}

export default function App() {
  const [api, setApi] = useState<DockviewApi | null>(null);
  const { mode, setMode, fluentTheme, dockviewClass, isDark } = useTheme();

  return (
    <FluentProvider theme={fluentTheme}>
      <AppInner
        api={api}
        setApi={setApi}
        dockviewClass={dockviewClass}
        mode={mode}
        setMode={setMode}
        isDark={isDark}
      />
    </FluentProvider>
  );
}

function AppInner({
  api,
  setApi,
  dockviewClass,
  mode,
  setMode,
  isDark,
}: {
  api: DockviewApi | null;
  setApi: (api: DockviewApi) => void;
  dockviewClass: string;
  mode: ThemeMode;
  setMode: (m: ThemeMode) => void;
  isDark: boolean;
}) {
  const toasterId = useId("cpf-toaster");
  const toastController = useToastController(toasterId);
  const styles = useStyles();

  // Sync body background and dockview theme class with current theme
  useEffect(() => {
    document.body.style.backgroundColor = isDark ? "#1e1e1e" : "#fafafa";
    document.body.style.colorScheme = isDark ? "dark" : "light";
  }, [isDark]);

  // Dockview className prop only applies on mount, so sync it imperatively
  useEffect(() => {
    const containers = document.querySelectorAll(
      ".dockview-theme-abyss, .dockview-theme-light",
    );
    containers.forEach((el) => {
      el.classList.remove("dockview-theme-abyss", "dockview-theme-light");
      el.classList.add(dockviewClass);
    });
  }, [dockviewClass]);

  // Persist layout on changes
  useEffect(() => {
    if (!api) return;
    const disposable = api.onDidLayoutChange(() => {
      try {
        localStorage.setItem(LAYOUT_KEY, JSON.stringify(api.toJSON()));
      } catch {
        // ignore quota errors
      }
    });
    return () => disposable.dispose();
  }, [api]);

  const onReady = (event: DockviewReadyEvent) => {
    const dv = event.api;
    setApi(dv);

    // Try restore saved layout
    const saved = localStorage.getItem(LAYOUT_KEY);
    if (saved) {
      try {
        dv.fromJSON(JSON.parse(saved));
      } catch {
        localStorage.removeItem(LAYOUT_KEY);
      }
    }

    // Ensure permanent panels always exist (guards against empty/corrupt layouts)
    ensurePermanentPanels(dv);
  };

  function ensurePermanentPanels(dv: DockviewApi) {
    if (!dv.getPanel("runs-list")) {
      dv.addPanel({
        id: "runs-list",
        component: "runs-list",
        title: "Runs",
        tabComponent: "permanent",
      });
    }
    if (!dv.getPanel("workflows-list")) {
      dv.addPanel({
        id: "workflows-list",
        component: "workflows-list",
        title: "Workflows",
        tabComponent: "permanent",
      });
    }
  }

  const onThemeChange: MenuProps["onCheckedValueChange"] = (_, data) => {
    const selected = data.checkedItems[0] as ThemeMode;
    if (selected) setMode(selected);
  };

  return (
    <DockviewApiContext.Provider value={api}>
      <ToasterContext.Provider value={toastController}>
        <div style={{ height: "100vh", width: "100vw" }}>
          <DockviewReact
            className={dockviewClass}
            onReady={onReady}
            components={panelComponents}
            tabComponents={tabComponents}
          />
        </div>

        {/* Theme selector */}
        <Menu
          checkedValues={{ theme: [mode] }}
          onCheckedValueChange={onThemeChange}
        >
          <MenuTrigger>
            <Button
              appearance="subtle"
              className={styles.themeButton}
              icon={<ThemeIcon mode={mode} isDark={isDark} />}
              title="Change theme"
            />
          </MenuTrigger>
          <MenuPopover>
            <MenuList>
              <MenuItemRadio name="theme" value="light" icon={<WeatherSunnyRegular />}>
                Light
              </MenuItemRadio>
              <MenuItemRadio name="theme" value="dark" icon={<WeatherMoonRegular />}>
                Dark
              </MenuItemRadio>
              <MenuItemRadio name="theme" value="system" icon={<DesktopRegular />}>
                System
              </MenuItemRadio>
            </MenuList>
          </MenuPopover>
        </Menu>

        <Toaster toasterId={toasterId} position="bottom-end" />
      </ToasterContext.Provider>
    </DockviewApiContext.Provider>
  );
}
