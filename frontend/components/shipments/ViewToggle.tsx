"use client";

import styles from "./shipmentCards.module.css";

export type ShipmentView = "cards" | "list";

type Props = {
  value: ShipmentView;
  onChange: (next: ShipmentView) => void;
};

export function ViewToggle({ value, onChange }: Props) {
  return (
    <div className={styles.viewSwitch} data-active={value} role="group" aria-label="Вид: карточки или список">
      <span className={styles.viewSwitchThumb} aria-hidden="true" />
      <button type="button" aria-pressed={value === "cards"} onClick={() => onChange("cards")}>
        Карточки
      </button>
      <button type="button" aria-pressed={value === "list"} onClick={() => onChange("list")}>
        Список
      </button>
    </div>
  );
}
