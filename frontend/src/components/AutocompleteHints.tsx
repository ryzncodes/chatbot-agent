import { useMemo } from "react";

import styles from "./AutocompleteHints.module.css";

interface Props {
  input: string;
  commands: string[];
}

function AutocompleteHints({ input, commands }: Props) {
  const active = useMemo(() => {
    if (!input.startsWith("/")) return null;
    const [command] = input.split(" ", 1);
    return commands.find((item) => item.startsWith(command));
  }, [input, commands]);

  if (!active || active === input.split(" ", 1)[0]) return null;

  return (
    <div className={styles.hints}>
      <span className={styles.label}>Hint</span>
      <span>{active}</span>
    </div>
  );
}

export default AutocompleteHints;
