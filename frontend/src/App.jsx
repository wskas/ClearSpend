import { useEffect, useState } from 'react';
import axios from 'axios';

function App() {
  const [message, setMessage] = useState('');

  useEffect(() => {
    axios.get('http://localhost:8000/subscriptions/')
      .then(response => {
        setMessage(response.data.message);
      })
      .catch(error => {
        console.error("Error fetching data:", error);
      });
  }, [message]);

  return (
    <div style={{ textAlign: 'center', marginTop: '50px' }}>
      <h1>Django + React App</h1>
      <p>Backend Status: <strong>{message || "Loading..."}</strong></p>
    </div>
  );
}

export default App;