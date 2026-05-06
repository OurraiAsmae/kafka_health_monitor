"""
Couche d'accès à Kafka.

Responsabilité unique : se connecter au cluster et lire les offsets
bruts (log-end-offset et committed-offset) pour chaque partition.
Le calcul du lag lui-même est fait dans lag_calculator.py.
"""
from confluent_kafka import Consumer, KafkaException
from confluent_kafka.admin import AdminClient, NewTopic
from .config_loader import CONFIG


def _make_admin() -> AdminClient:
    """Crée un client Admin Kafka (lecture des topics/partitions)."""
    return AdminClient({
        "bootstrap.servers": CONFIG["kafka"]["bootstrap_servers"]
    })


def _make_consumer(group_id: str = "_kafka_health_monitor_probe") -> Consumer:
    """
    Crée un Consumer temporaire utilisé uniquement pour lire les offsets.
    group_id spécial pour ne pas polluer les vrais consumer groups.
    """
    return Consumer({
        "bootstrap.servers": CONFIG["kafka"]["bootstrap_servers"],
        "group.id": group_id,
        "enable.auto.commit": False,   # lecture seule, on ne commit rien
        "auto.offset.reset": "latest",
    })


def get_topics() -> list[str]:
    """
    Retourne la liste de tous les topics du cluster,
    en excluant les topics internes (__consumer_offsets, etc.)
    et ceux listés dans exclude_topics du config.
    """
    admin = _make_admin()
    metadata = admin.list_topics(timeout=10)

    exclude = set(CONFIG.get("exclude_topics", []))

    topics = [
        name
        for name in metadata.topics.keys()
        if not name.startswith("_")   # topics internes Kafka
        and name not in exclude
    ]
    return sorted(topics)


def get_consumer_groups() -> list[str]:
    """
    Retourne tous les consumer groups actifs ou inactifs.
    Exclut le groupe sonde du monitor lui-même.
    """
    admin = _make_admin()
    groups_result = admin.list_consumer_groups()

    exclude = set(CONFIG.get("exclude_groups", []))
    exclude.add("_kafka_health_monitor_probe")

    groups = []
    for group in groups_result.result().valid:
        if group.group_id not in exclude:
            groups.append(group.group_id)

    return sorted(groups)


def get_log_end_offsets(topic: str) -> dict[int, int]:
    """
    Retourne le Log-End-Offset (dernier message produit) pour chaque
    partition d'un topic.

    Le LEO représente la position de la "tête" du topic — c'est-à-dire
    combien de messages ont été écrits au total dans cette partition.

    Retourne : {partition_id: log_end_offset}
    """
    consumer = _make_consumer()
    try:
        # Récupère les métadonnées du topic pour connaître les partitions
        metadata = consumer.list_topics(topic, timeout=10)
        partitions = metadata.topics[topic].partitions

        from confluent_kafka import TopicPartition

        # Construit la liste des TopicPartition à interroger
        topic_partitions = [
            TopicPartition(topic, partition_id)
            for partition_id in partitions.keys()
        ]

        # query les offsets de fin (OFFSET_END = position du prochain message)
        # On utilise -1 (OFFSET_END) comme offset pour indiquer qu'on veut la fin
        end_offsets = {}
        for tp in topic_partitions:
            low, high = consumer.get_watermark_offsets(tp, timeout=5)
            # high = log-end-offset = nombre total de messages dans cette partition
            end_offsets[tp.partition] = high

        return end_offsets

    finally:
        consumer.close()


def get_committed_offsets(group_id: str, topic: str, bootstrap_servers: str) -> dict[int, int]:
    """
    Lit les committed offsets via AdminClient — plus fiable que Consumer.
    """
    from confluent_kafka import TopicPartition
    from confluent_kafka.admin import AdminClient

    admin = AdminClient({"bootstrap.servers": bootstrap_servers})

    try:
        # Récupère les partitions du topic
        metadata = admin.list_topics(topic, timeout=10)
        partitions = metadata.topics[topic].partitions
        topic_partitions = [TopicPartition(topic, pid) for pid in partitions.keys()]

        # list_consumer_group_offsets lit les vrais committed offsets
        result = admin.list_consumer_group_offsets(
            [{"group.id": group_id, "partitions": topic_partitions}]
        )

        committed_offsets = {}
        for res in result:
            future = result[res]
            group_result = future.result()
            for tp, offset_info in group_result.topic_partitions.items():
                offset = offset_info.offset if offset_info.offset >= 0 else 0
                committed_offsets[tp.partition] = offset

        return committed_offsets

    except Exception as e:
        print(f"[kafka_client] Erreur committed offsets {group_id}/{topic}: {e}")
        return {}
    
    
def get_consumer_group_state(group_id: str, bootstrap_servers: str) -> str:
    """
    Retourne l'état actuel d'un consumer group.

    États possibles :
    - Stable          : consomme normalement
    - Empty           : groupe vide, aucun consumer connecté
    - Dead            : groupe supprimé ou inexistant
    - PreparingRebalance  : rebalancing en cours
    - CompletingRebalance : rebalancing en finalisation

    Utilise l'AdminClient Kafka pour lire les métadonnées du groupe.
    """
    try:
        admin = AdminClient({"bootstrap.servers": bootstrap_servers})
        result = admin.describe_consumer_groups([group_id])

        if group_id not in result:
            return "Unknown"

        group_future = result[group_id]
        group_info   = group_future.result()
        state        = str(group_info.state)

        # Normalise le format (confluent-kafka retourne "ConsumerGroupState.Stable")
        if "." in state:
            state = state.split(".")[-1]

        return state

    except Exception as e:
        print(f"[kafka_client] Erreur get_state {group_id}: {e}")
        return "Unknown"


def get_all_group_states(bootstrap_servers: str, group_ids: list[str]) -> dict[str, str]:
    """
    Retourne l'état de plusieurs consumer groups en un seul appel Admin.
    Plus efficace que d'appeler get_consumer_group_state() en boucle.

    Retourne : {group_id: state_string}
    """
    if not group_ids:
        return {}

    try:
        admin  = AdminClient({"bootstrap.servers": bootstrap_servers})
        result = admin.describe_consumer_groups(group_ids)

        states = {}
        for gid in group_ids:
            if gid in result:
                try:
                    info        = result[gid].result()
                    state       = str(info.state)
                    if "." in state:
                        state = state.split(".")[-1]
                    states[gid] = state
                except Exception:
                    states[gid] = "Unknown"
            else:
                states[gid] = "Unknown"

        return states

    except Exception as e:
        print(f"[kafka_client] Erreur get_all_states: {e}")
        return {gid: "Unknown" for gid in group_ids}