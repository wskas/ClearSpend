// import { useEffect, useState } from 'react';
// import axios from 'axios';
import { Sidebar } from "./components/layout/Sidebar";
import { Header } from "./components/layout/Header";
import { KPICards } from "./components/KPICards";
import { ProjectionChart } from "./components/ProjectionChart";
import { SubscriptionsTable } from "./components/SubscriptionsTable";

function App() {

  // useEffect(() => {
  //   axios.get('http://localhost:8000/subscriptions/')
  //     .then(response => {
  //       setMessage(response.data.message);
  //     })
  //     .catch(error => {
  //       console.error("Error fetching data:", error);
  //     });
  // }, [message]);

  return (
    <div className="h-screen bg-[#F1F5F9] font-sans text-slate-900 flex overflow-hidden">
      <Sidebar />
      <main className="flex-1 flex flex-col h-full overflow-hidden">
        <Header />
        <div className="flex-1 p-6 md:p-10 flex flex-col gap-8 overflow-y-auto">
          <KPICards />
          <ProjectionChart />
          <SubscriptionsTable />
        </div>
      </main>
    </div>
  );
}

export default App;