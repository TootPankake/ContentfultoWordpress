<?php
/*
Plugin Name: My Custom Functions
Description: A plugin to add custom functions independent of the theme.
Version: 1.0
Author: Emre Gumus
*/

add_filter( 'rest_enabled', '__return_true' );

// Add a meta box for the metadata ID
function add_metadata_id_meta_box() {
    add_meta_box(
        'metadata_id_meta_box', // ID
        'Metadata ID', // Title
        'metadata_id_meta_box_callback', // Callback
        'page', // Screen (post type)
        'side', // Context
        'high' // Priority
    );
}
add_action('add_meta_boxes', 'add_metadata_id_meta_box');

function metadata_id_meta_box_callback($post) {
    // Add a nonce field for security
    wp_nonce_field('save_metadata_id', 'metadata_id_nonce');

    // Get the current value of the metadata ID
    $metadata_id = get_post_meta($post->ID, '_metadata_id', true);

    echo '<label for="metadata_id">Metadata ID: </label>';
    echo '<input type="text" id="metadata_id" name="metadata_id" value="' . esc_attr($metadata_id) . '" />';
}

function save_metadata_id($post_id) {
    // Check if nonce is set
    if (!isset($_POST['metadata_id_nonce'])) {
        return $post_id;
    }

    // Verify the nonce
    if (!wp_verify_nonce($_POST['metadata_id_nonce'], 'save_metadata_id')) {
        return $post_id;
    }

    // Check if this is an autosave
    if (defined('DOING_AUTOSAVE') && DOING_AUTOSAVE) {
        return $post_id;
    }

    // Check user permissions
    if (isset($_POST['post_type']) && 'page' === $_POST['post_type']) {
        if (!current_user_can('edit_page', $post_id)) {
            return $post_id;
        }
    } else {
        if (!current_user_can('edit_post', $post_id)) {
            return $post_id;
        }
    }

    // Sanitize the user input
    $metadata_id = sanitize_text_field($_POST['metadata_id']);

    // Update the metadata ID
    update_post_meta($post_id, '_metadata_id', $metadata_id);
}
add_action('save_post', 'save_metadata_id');


// Add custom columns to the pages screen
function add_metadata_id_column($columns) {
    $columns['metadata_id'] = 'Metadata ID';
    return $columns;
}
add_filter('manage_page_posts_columns', 'add_metadata_id_column');

// Populate the custom columns with data
function metadata_id_column_content($column, $post_id) {
    if ($column === 'metadata_id') {
        $metadata_id = get_post_meta($post_id, '_metadata_id', true);
        echo esc_html($metadata_id);
    }
}
add_action('manage_page_posts_custom_column', 'metadata_id_column_content', 10, 2);

// Make the custom columns sortable
function metadata_id_column_sortable($columns) {
    $columns['metadata_id'] = 'metadata_id';
    return $columns;
}
add_filter('manage_edit-page_sortable_columns', 'metadata_id_column_sortable');

// Order the posts by metadata ID when sorting
function metadata_id_orderby($query) {
    if (!is_admin() || !$query->is_main_query()) {
        return;
    }

    if ('metadata_id' === $query->get('orderby')) {
        $query->set('meta_key', '_metadata_id');
        $query->set('orderby', 'meta_value');
    }
}
add_action('pre_get_posts', 'metadata_id_orderby');

// Register metadata for the REST API
function register_metadata_id_for_rest_api() {
    register_meta('post', '_metadata_id', [
        'show_in_rest' => true,
        'type' => 'string',
        'single' => true,
        'sanitize_callback' => 'sanitize_text_field',
        'auth_callback' => function() {
            return current_user_can('edit_posts');
        }
    ]);
}
add_action('init', 'register_metadata_id_for_rest_api');

function add_categories_to_pages() {
    register_taxonomy_for_object_type('category', 'page');
}
add_action('init', 'add_categories_to_pages');

function add_metadata_id_to_categories() {
    register_rest_field(
        'category', // The taxonomy to which you want to add the custom field
        'metadata_id', // The name of the custom field in the REST API
        array(
            'get_callback'    => 'get_metadata_id_for_category',
            'update_callback' => 'update_metadata_id_for_category',
            'schema'          => array(
                'description' => __('Metadata ID for the category'),
                'type'        => 'string',
                'context'     => array('view', 'edit'),
            ),
        )
    );
}
add_action('rest_api_init', 'add_metadata_id_to_categories');

// Callback function to get the metadata ID
function get_metadata_id_for_category($object, $field_name, $request) {
    return get_term_meta($object['id'], 'metadata_id', true);
}

// Callback function to update the metadata ID
function update_metadata_id_for_category($value, $object, $field_name) {
    if (!empty($value)) {
        update_term_meta($object->term_id, 'metadata_id', sanitize_text_field($value));
    }
}

// Add a custom column to the category list table
function add_metadata_id_column_category($columns) {
    $columns['metadata_id'] = __('Metadata ID');
    return $columns;
}
add_filter('manage_edit-category_columns', 'add_metadata_id_column_category');

// Populate the custom column with metadata values
function fill_metadata_id_column_category($content, $column_name, $term_id) {
    if ($column_name === 'metadata_id') {
        $metadata_id = get_term_meta($term_id, 'metadata_id', true);
        if (!empty($metadata_id)) {
            $content = esc_attr($metadata_id);
        } else {
            $content = __('No Metadata ID', 'your-text-domain');
        }
    }
    return $content;
}

function add_category_to_page_permalink($post_link, $post) {
    if ($post->post_type == 'page') {
        // Get the categories for the page
        $categories = get_the_category($post->ID);
        if ($categories) {
            $category = $categories[0]; // Assuming you want to use the first category
            $post_link = str_replace('%category%', $category->slug, $post_link);
        }
    }
    return $post_link;
}
add_filter('page_link', 'add_category_to_page_permalink', 10, 2);

function custom_rewrite_rules() {
    add_rewrite_rule(
        '^(.+?)/([^/]+)?$',
        'index.php?pagename=$matches[1]&category_name=$matches[2]',
        'top'
    );
}
add_action('init', 'custom_rewrite_rules');
add_filter('manage_category_custom_column', 'fill_metadata_id_column_category', 10, 3);
