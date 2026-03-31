import * as signalR from '@microsoft/signalr'

let connection: signalR.HubConnection | null = null

export function getSignalRConnection(): signalR.HubConnection {
  if (!connection) {
    connection = new signalR.HubConnectionBuilder()
      .withUrl('/hubs/signals', {
        accessTokenFactory: () => localStorage.getItem('tradeos_token') ?? '',
      })
      .withAutomaticReconnect()
      .configureLogging(signalR.LogLevel.Warning)
      .build()
  }
  return connection
}

export async function startSignalR(): Promise<void> {
  const conn = getSignalRConnection()
  if (conn.state === signalR.HubConnectionState.Disconnected) {
    await conn.start()
  }
}

export async function stopSignalR(): Promise<void> {
  if (connection) {
    await connection.stop()
  }
}
