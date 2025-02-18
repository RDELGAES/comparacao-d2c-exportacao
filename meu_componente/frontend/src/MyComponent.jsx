import React, { useEffect } from "react";
import { Streamlit } from "streamlit-component-lib";

const MyComponent = (props) => {
  useEffect(() => {
    Streamlit.setComponentValue("Valor Retornado!");
  }, []);

  return (
    <div>
      <h3>{props.label}</h3>
      <button onClick={() => Streamlit.setComponentValue("Botão Clicado!")}>
        {props.label}
      </button>
    </div>
  );
};

export default MyComponent;






