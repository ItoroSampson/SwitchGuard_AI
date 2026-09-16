import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { RefreshCw, ArrowLeft } from 'lucide-react';

const API_BASE = "http://127.0.0.1:8000/api/v1";

const MONITORED_BANKS = [
  "GTBank",
  "Zenith Bank",
  "Access Bank",
  "First Bank",
  "UBA",
  "Wema Bank",
  "Sterling Bank",
  "Stanbic Bank",
  "Polaris Bank"
];


const normalizeBankName = (name = "") => {
  const n = name.toLowerCase();
  if (n.includes("gtb") || n.includes("gtbank") || n.includes("guaranty")) return "gtbank";
  if (n.includes("zenith")) return "zenith bank";
  if (n.includes("access")) return "access bank";
  if (n.includes("first")) return "first bank";
  if (n.includes("uba") || n.includes("united bank")) return "uba";
  if (n.includes("wema")) return "wema bank";
  if (n.includes("sterling")) return "sterling bank";
  if (n.includes("stanbic")) return "stanbic bank";
  if (n.includes("polaris")) return "polaris bank";
  return n;
};

function App() {
  const [routesData, setRoutesData] = useState([]);
  const [timeRange, setTimeRange] = useState("Last 5 minutes");
  const [activeTab, setActiveTab] = useState("Withdraw");
  const [loading, setLoading] = useState(false);

  const fetchTelemetry = async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API_BASE}/routes/health`);
      const rawRoutes = res.data.routes || [];

      const mapped = MONITORED_BANKS.map((bankName) => {
        const targetBankNorm = normalizeBankName(bankName);

        const getSchemeSuccessRate = (scheme) => {
          
          const matches = rawRoutes.filter((r) => {
            const routeBankNorm = normalizeBankName(r.bank || "");
            const bankMatch = routeBankNorm === targetBankNorm || 
                              JSON.stringify(r).toLowerCase().includes(targetBankNorm);
            
            const cardTypeStr = (r.card_type || "").toLowerCase();
            const schemeMatch = cardTypeStr.includes(scheme.toLowerCase());

            return bankMatch && schemeMatch;
          });

          if (matches.length === 0) return "N/A";

          
          const totalFailure = matches.reduce((acc, curr) => {
            const failVal = curr.failure_rate !== undefined ? curr.failure_rate : (curr.fail_rate_pct / 100);
            return acc + failVal;
          }, 0);

          const avgFailureRate = totalFailure / matches.length;
          const successRate = (1 - avgFailureRate) * 100;

          return parseFloat(successRate.toFixed(2));
        };

        return {
          bank: bankName,
          master: getSchemeSuccessRate("Mastercard"),
          visa: getSchemeSuccessRate("Visa"),
          verve: getSchemeSuccessRate("Verve"),
        };
      });

      setRoutesData(mapped);
    } catch (err) {
      console.error("Failed to fetch dynamic telemetry:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTelemetry();
    const interval = setInterval(fetchTelemetry, 3000);
    return () => clearInterval(interval);
  }, []);

  const renderValueBadge = (val) => {
    if (val === "N/A" || val === undefined) {
      return <span className="text-slate-400 font-normal">N/A</span>;
    }
    const num = parseFloat(val);
    
    // High Risk badge (Red) <= 50.0% success
    if (num <= 50.0) {
      return (
        <span className="bg-red-500 text-white font-semibold px-2 py-1 rounded text-xs inline-block w-14 text-center">
          {num.toFixed(2)}
        </span>
      );
    }
    // Medium Risk badge (Orange) between 50.1% and 85.0% success
    if (num > 50.0 && num <= 85.0) {
      return (
        <span className="bg-orange-400 text-white font-semibold px-2 py-1 rounded text-xs inline-block w-14 text-center">
          {num.toFixed(2)}
        </span>
      );
    }
    // Healthy (Plain text) > 85.0% success
    return <span className="text-slate-700 font-medium">{num.toFixed(2)}</span>;
  };

  return (
    <div className="min-h-screen bg-slate-100 flex justify-center items-center p-0 md:p-4 font-sans">
      <div className="w-full max-w-md bg-white min-h-screen md:min-h-[800px] md:rounded-2xl shadow-xl flex flex-col overflow-hidden border border-slate-200">
        
        {/* Header Bar */}
        <div className="px-4 pt-4 pb-2 flex items-center justify-between border-b border-slate-100">
          <div className="flex items-center gap-2">
            <ArrowLeft className="w-5 h-5 text-slate-700 cursor-pointer" />
            <h1 className="text-lg font-bold text-slate-800 tracking-tight">Bank Success Rate</h1>
          </div>
        </div>

        <p className="px-4 py-2 text-xs text-slate-400">
          Please check the status when you run into transaction errors.
        </p>

        {/* Controls */}
        <div className="px-4 py-2 flex items-center justify-between text-xs text-slate-600 border-b border-slate-100">
          <select 
            value={timeRange} 
            onChange={(e) => setTimeRange(e.target.value)}
            className="bg-slate-50 border border-slate-200 rounded px-2 py-1 text-slate-700 outline-none">
            <option>Last 5 minutes</option>
            <option>Last 15 minutes</option>
            <option>Last 1 hour</option>
          </select>

          <button onClick={fetchTelemetry} className="p-1 hover:bg-slate-100 rounded">
            <RefreshCw className={`w-4 h-4 text-slate-500 ${loading ? 'animate-spin' : ''}`} />
          </button>

          <select className="bg-slate-50 border border-slate-200 rounded px-2 py-1 text-slate-700 outline-none">
            <option>OFF</option>
            <option>ON</option>
          </select>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-slate-200 text-sm font-medium">
          <button
            onClick={() => setActiveTab("Withdraw")}
            className={`flex-1 py-3 text-center transition-all ${
              activeTab === "Withdraw"
                ? "text-indigo-600 border-b-2 border-indigo-600 font-semibold"
                : "text-slate-400"
            }`}>
            Withdraw
          </button>
          <button
            onClick={() => setActiveTab("Transfer")}
            className={`flex-1 py-3 text-center transition-all ${
              activeTab === "Transfer"
                ? "text-indigo-600 border-b-2 border-indigo-600 font-semibold"
                : "text-slate-400"
            }`}>
            Transfer
          </button>
        </div>

        {/* Risk Legend */}
        <div className="px-4 py-2 flex gap-4 text-xs font-medium border-b border-slate-100 bg-slate-50">
          <div className="flex items-center gap-1">
            <span className="w-3 h-1 bg-red-500 rounded-sm"></span>
            <span className="text-red-500">High Risk</span>
          </div>
          <div className="flex items-center gap-1">
            <span className="w-3 h-1 bg-orange-400 rounded-sm"></span>
            <span className="text-orange-400">Medium Risk</span>
          </div>
        </div>

        {/* Data Table */}
        <div className="flex-1 overflow-y-auto">
          <table className="w-full text-xs text-left">
            <thead className="bg-slate-50 text-slate-400 font-medium border-b border-slate-100">
              <tr>
                <th className="py-3 px-4 font-normal">Bank</th>
                <th className="py-3 px-2 text-center font-normal">Master(%)</th>
                <th className="py-3 px-2 text-center font-normal">Visa(%)</th>
                <th className="py-3 px-2 text-center font-normal">Verve(%)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {routesData.map((row, idx) => (
                <tr key={idx} className="hover:bg-slate-50/80 transition-colors">
                  <td className="py-3 px-4 text-indigo-900 font-medium truncate max-w-[120px]">
                    {row.bank}
                  </td>
                  <td className="py-3 px-2 text-center">{renderValueBadge(row.master)}</td>
                  <td className="py-3 px-2 text-center">{renderValueBadge(row.visa)}</td>
                  <td className="py-3 px-2 text-center">{renderValueBadge(row.verve)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

      </div>
    </div>
  );
}

export default App;