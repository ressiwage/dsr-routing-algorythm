import logo from './logo.svg';
import './App.css';
import React, { useRef } from 'react';
import { useEffect, useState } from 'react';
import { GraphCanvas } from "reagraph";
import chroma from 'chroma-js';

function filterUniqueById(arr) {
  const seen = new Set();
  return arr.filter(obj => {
    if (seen.has(obj.id)) {
      return false;
    }
    seen.add(obj.id);
    return true;
  });
}

function filterUnique(arr) {
  const seen = new Set();
  return arr.filter(obj => {
    if (seen.has(obj)) {
      return false;
    }
    seen.add(obj);
    return true;
  });
}


function filterUniqueBySD(arr) {
  const seen = new Set();
  const result = [];
  
  // Проходим по всем путям в исходном порядке
  for (const path of arr) {
    if (path.length === 0) continue;
    
    // Берем первый и последний элементы пути
    const firstElement = path[0];
    const lastElement = path[path.length - 1];
    
    // Создаем уникальный ключ на основе первого и последнего элементов
    const key = `${firstElement.port || firstElement}-${lastElement.port || lastElement}`;
    
    // Если такого ключа еще нет - добавляем путь в результат
    if (!seen.has(key)) {
      seen.add(key);
      result.push(path);
    }
  }
  
  return result;
}
function App() {
  var [refresh, setRefresh] = useState(0);
  var [data, setData] = useState({})
  var [paths, setPaths] = useState([]);
  var [pathsDisplay, setPathsDisplay] = useState([]);
  var [nodesData, setNodesData] = useState({ nodes: [], edges: [] })

  useEffect(() => {
    var nodes = [];
    var edges = [];
    var rg = chroma.scale(['green', 'red'])
    var rgb_ = chroma.scale(['green', 'blue', 'red'])

    var portsToNames = {}

    function rec(serv) {
      portsToNames[serv.port] = serv.name
      nodes.push({ id: serv.name, label: serv.name, fill: rg(Math.min(1, serv.load / serv.cpu)).hex() })
      if (serv.children) {
        serv.children.forEach(element => {
          edges.push({ id: `${serv.name}->${element.name}`, source: serv.name, target: element.name, label: ' ' })
          rec(element)
        })
      };
    };
    rec(data);

    const unique = filterUniqueBySD(paths)
    unique.map((path, path_index) => {
      path.map((node, index) => {
        if (index > 0) {
          console.log(path[index-1], node)
          edges.push({ id: `${portsToNames[path[index - 1]]}->${portsToNames[node]}`, 
            source:portsToNames[path[index - 1]], 
            target:portsToNames[node], 
            fill: rgb_(Math.random()).hex(),
            label:" "
          })
          return 1
        }
      })
      console.log(path.join('->'))
      setPathsDisplay(pathsDisplay=>filterUnique([...pathsDisplay, path.map(p=>portsToNames[p]).join('->')]))
    })
    edges.reverse()
    console.log(edges)
    setNodesData({ nodes: filterUniqueById(nodes), edges: filterUniqueById(edges) })
  }, [data, paths])

  useEffect(() => {
    console.log("Updated paths:", paths);
  }, [paths]);

  useEffect(() => {
    fetch("http://localhost:7999/echo_ws?" + new URLSearchParams({
      receiver: "ws://localhost:7999/ws"
    }).toString(), { method: "GET", headers: { 'accept': 'application/json' } }).then(r => r.json()).then(json => {
      // setTimeout(() => { setRefresh(refresh + 1) }, 3000)
    })
  }, [refresh])

  useEffect(() => {
    const socket = new WebSocket('ws://localhost:7999/ws');

    socket.onopen = function () {
      console.log('Соединение установлено (клиент слушает)');
    };

    socket.onmessage = function (event) {
      console.log(`Получено сообщение: ${event.data}`);
      try {
        const parsedData = JSON.parse(event.data);
        switch (parsedData.route) {
          case 'echo_back':
            setData(parsedData.payload);
            console.log(parsedData.payload)
            break;
          case "new_path":
            // ИСПРАВЛЕНИЕ: правильно добавляем новый путь
            setPaths(prevPaths => filterUniqueBySD([...prevPaths, parsedData.payload.new]));
            console.log("Added new path:", parsedData.payload.new);
            break;
        }
      } catch {
        setData({ raw: event.data });
      }
    };

    socket.onclose = function () {
      console.log('Соединение закрыто');
    };

    return () => socket.close();
  }, []);

  return (
    <div className="App">
      {JSON.stringify(data)}
      {JSON.stringify(nodesData)}
      <div style={{width:'50%', zIndex:1, position: 'absolute', top:0}}>
        {pathsDisplay.map(pd=>{return <h3>{pd}</h3>})}
        </div>
      <GraphCanvas

nodes={nodesData.nodes}
        edges={nodesData.edges}
      />
    </div>
  );
}

export default App;