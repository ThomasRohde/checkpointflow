import { useState, useCallback, useContext } from "react";
import {
  Button,
  Toast,
  ToastBody,
  ToastTitle,
  makeStyles,
} from "@fluentui/react-components";
import {
  CopyRegular,
  CheckmarkRegular,
} from "@fluentui/react-icons";
import { ToasterContext } from "../App";

const useStyles = makeStyles({
  button: {
    minWidth: "auto",
  },
});

export function CopyButton({
  text,
  label = "Copy",
}: {
  text: string;
  label?: string;
}) {
  const [copied, setCopied] = useState(false);
  const styles = useStyles();
  const toastController = useContext(ToasterContext);

  const handleCopy = useCallback(
    async (e: React.MouseEvent) => {
      e.stopPropagation();
      try {
        await navigator.clipboard.writeText(text);
        setCopied(true);
        toastController?.dispatchToast(
          <Toast>
            <ToastTitle>Copied to clipboard</ToastTitle>
          </Toast>,
          { intent: "success" },
        );
        setTimeout(() => setCopied(false), 2000);
      } catch {
        toastController?.dispatchToast(
          <Toast>
            <ToastBody>Failed to copy</ToastBody>
          </Toast>,
          { intent: "error" },
        );
      }
    },
    [text, toastController],
  );

  return (
    <Button
      appearance="subtle"
      size="small"
      icon={copied ? <CheckmarkRegular /> : <CopyRegular />}
      onClick={handleCopy}
      aria-label={label}
      title={label}
      className={styles.button}
    />
  );
}
